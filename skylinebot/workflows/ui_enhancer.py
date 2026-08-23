import asyncio
import re
from typing import Iterable

import discord


_PATCHED = False


def _starts_with_emoji(text: str) -> bool:
    if not text:
        return False
    value = str(text).strip()
    if not value:
        return False
    # Custom emoji: <:name:id> / <a:name:id>
    if re.match(r"^<a?:\w+:\d+>", value):
        return True
    # Common unicode emoji ranges (loose check)
    first = value[0]
    return ord(first) >= 0x2600


def _pick_emoji_from_text(text: str, fallback: str = "✨") -> str:
    value = str(text or "").lower()
    keyword_map = [
        (("help", "guide", "manual", "คำสั่ง", "วิธีใช้"), "📘"),
        (("welcome", "welcomer", "ต้อนรับ"), "👋"),
        (("ticket", "ทิกเก็ต"), "🎫"),
        (("music", "เพลง", "play", "queue"), "🎵"),
        (("security", "antinuke", "ความปลอดภัย"), "🛡️"),
        (("automod", "antispam", "antilink"), "🚫"),
        (("settings", "setup", "config", "ตั้งค่า"), "⚙️"),
        (("invite", "เชิญ"), "🔗"),
        (("support", "ซัพพอร์ต"), "🆘"),
        (("success", "done", "สำเร็จ"), "✅"),
        (("warning", "warn", "เตือน"), "⚠️"),
        (("error", "fail", "ผิดพลาด"), "❌"),
        (("info", "ข้อมูล"), "ℹ️"),
    ]
    for keywords, emoji in keyword_map:
        if any(keyword in value for keyword in keywords):
            return emoji
    return fallback


def _prefix_text_with_emoji(text: str, emoji: str) -> str:
    value = str(text or "").strip()
    if not value:
        return value
    if _starts_with_emoji(value):
        return value
    return f"{emoji} {value}"


def _beautify_embed(embed: discord.Embed | None) -> discord.Embed | None:
    if not isinstance(embed, discord.Embed):
        return embed

    if embed.title:
        emoji = _pick_emoji_from_text(embed.title)
        embed.title = _prefix_text_with_emoji(embed.title, emoji)

    if embed.fields:
        for index, field in enumerate(embed.fields):
            name = getattr(field, "name", "")
            if not name:
                continue
            emoji = _pick_emoji_from_text(name, fallback="🔹")
            embed.set_field_at(
                index,
                name=_prefix_text_with_emoji(name, emoji),
                value=field.value,
                inline=field.inline,
            )
    return embed


def _beautify_button(button: discord.ui.Button) -> None:
    if getattr(button, "emoji", None) is not None:
        return
    label = str(getattr(button, "label", "") or "")
    if label:
        button.emoji = _pick_emoji_from_text(label, fallback="🔸")
        return
    url = str(getattr(button, "url", "") or "")
    if url:
        button.emoji = "🔗"
        return
    style = getattr(button, "style", None)
    style_map = {
        discord.ButtonStyle.success: "✅",
        discord.ButtonStyle.danger: "🛑",
        discord.ButtonStyle.primary: "🔹",
        discord.ButtonStyle.secondary: "🔸",
        discord.ButtonStyle.link: "🔗",
    }
    button.emoji = style_map.get(style, "🔹")


def _beautify_view(view: discord.ui.View | None) -> discord.ui.View | None:
    if view is None or not hasattr(view, "children"):
        return view
    for item in list(view.children):
        if isinstance(item, discord.ui.Button):
            _beautify_button(item)
    return view


def _normalize_payload_kwargs(kwargs: dict) -> dict:
    if "embed" in kwargs and kwargs["embed"] is not None:
        kwargs["embed"] = _beautify_embed(kwargs["embed"])
    if "embeds" in kwargs and kwargs["embeds"]:
        kwargs["embeds"] = [_beautify_embed(embed) for embed in kwargs["embeds"]]
    if "view" in kwargs and kwargs["view"] is not None:
        kwargs["view"] = _beautify_view(kwargs["view"])
    return kwargs


def patch_discord_ui() -> None:
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    # 1) channel.send / ctx.send pipeline
    original_messageable_send = discord.abc.Messageable.send

    async def patched_messageable_send(self, *args, **kwargs):
        kwargs = _normalize_payload_kwargs(kwargs)
        if "view" in kwargs and kwargs["view"] is None:
            kwargs.pop("view", None)
        return await original_messageable_send(self, *args, **kwargs)

    discord.abc.Messageable.send = patched_messageable_send

    # 2) message.edit
    original_message_edit = discord.Message.edit

    async def patched_message_edit(self, *args, **kwargs):
        kwargs = _normalize_payload_kwargs(kwargs)
        return await original_message_edit(self, *args, **kwargs)

    discord.Message.edit = patched_message_edit

    # 3) interaction response send/edit
    original_interaction_send = discord.InteractionResponse.send_message
    original_interaction_edit = discord.InteractionResponse.edit_message

    async def patched_interaction_send(self, *args, **kwargs):
        kwargs = _normalize_payload_kwargs(kwargs)
        # discord.py expects MISSING (not None) for view in InteractionResponse.send_message.
        # Passing view=None can raise AttributeError on some versions.
        if "view" in kwargs and kwargs["view"] is None:
            kwargs.pop("view", None)
        return await original_interaction_send(self, *args, **kwargs)

    async def patched_interaction_edit(self, *args, **kwargs):
        kwargs = _normalize_payload_kwargs(kwargs)
        return await original_interaction_edit(self, *args, **kwargs)

    discord.InteractionResponse.send_message = patched_interaction_send
    discord.InteractionResponse.edit_message = patched_interaction_edit

    # 4) followup.send / webhook.send
    original_webhook_send = discord.Webhook.send

    async def patched_webhook_send(self, *args, **kwargs):
        kwargs = _normalize_payload_kwargs(kwargs)
        delete_after = kwargs.pop("delete_after", None)
        ephemeral = bool(kwargs.get("ephemeral", False))
        if delete_after is not None and not ephemeral:
            # Webhook.send does not support delete_after on some discord.py versions.
            # Force wait=True so we can delete the sent message ourselves.
            kwargs.setdefault("wait", True)
        if "view" in kwargs and kwargs["view"] is None:
            kwargs.pop("view", None)
        message = await original_webhook_send(self, *args, **kwargs)

        if delete_after is not None and not ephemeral and message is not None:
            try:
                delay = max(0.0, float(delete_after))
            except (TypeError, ValueError):
                delay = 0.0

            async def _delete_later():
                await asyncio.sleep(delay)
                try:
                    await message.delete()
                except Exception:
                    return

            asyncio.create_task(_delete_later())

        return message

    discord.Webhook.send = patched_webhook_send
