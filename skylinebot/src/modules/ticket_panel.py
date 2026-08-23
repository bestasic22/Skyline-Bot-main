import discord
from discord.ext import commands
import storage.ticket_settings
import storage.tickets
from skylinebot.style import color
import traceback
import json
import re

from skylinebot.memory.cache import cache
from skylinebot.src.checks import checks

from skylinebot.console.logging import logger

from skylinebot.engine.bot_runtime import AutoShardedBot
import storage
import datetime

import asyncio
from pathlib import Path

from skylinebot.utils import chat_exporter

from io import BytesIO


_CUSTOM_EMOJI_NAME_RE = re.compile(r"^[A-Za-z0-9_]{2,32}$")


def _parse_json_field(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except Exception:
            return default
    return default


def _support_roles(value):
    raw = _parse_json_field(value, [])
    if not isinstance(raw, list):
        return []
    out = []
    for role_id in raw:
        try:
            out.append(int(role_id))
        except Exception:
            continue
    return out


def _build_layout_with_actions(markdown_lines, actions, timeout=None):
    view = discord.ui.LayoutView(timeout=timeout)
    container = discord.ui.Container()
    for line in markdown_lines:
        if line:
            container.add_item(discord.ui.TextDisplay(line))
    if actions:
        row = discord.ui.ActionRow()
        for item in actions:
            row.add_item(item)
        container.add_item(row)
    view.add_item(container)
    return view


def _safe_text(value, fallback=""):
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    if isinstance(fallback, str):
        return fallback.strip()
    if fallback is None:
        return ""
    try:
        return str(fallback).strip()
    except Exception:
        return ""


def _safe_int(value, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(str(value).strip())
    except Exception:
        return default


def _get_cached_channel_or_thread(guild: discord.Guild, channel_id: int):
    if not guild or channel_id <= 0:
        return None
    try:
        getter = getattr(guild, "get_channel_or_thread", None)
        if callable(getter):
            resolved = getter(channel_id)
            if resolved:
                return resolved
    except Exception:
        pass
    try:
        resolved = guild.get_channel(channel_id)
        if resolved:
            return resolved
    except Exception:
        pass
    try:
        getter = getattr(guild, "get_thread", None)
        if callable(getter):
            resolved = getter(channel_id)
            if resolved:
                return resolved
    except Exception:
        pass
    return None


async def _resolve_channel_with_fetch(
    *,
    bot: AutoShardedBot,
    guild: discord.Guild,
    channel_id_raw,
    allow_cross_guild: bool = False,
):
    channel_id = _safe_int(channel_id_raw, 0)
    if channel_id <= 0:
        return None, channel_id, False

    expected_guild_id = getattr(guild, "id", None)

    def _same_guild(candidate) -> bool:
        candidate_guild_id = getattr(getattr(candidate, "guild", None), "id", None)
        if expected_guild_id is None:
            return True
        return candidate_guild_id in (None, expected_guild_id)

    channel = _get_cached_channel_or_thread(guild, channel_id)
    if channel:
        return channel, channel_id, _same_guild(channel)

    try:
        bot_cached = bot.get_channel(channel_id)
    except Exception:
        bot_cached = None
    if bot_cached:
        same_guild = _same_guild(bot_cached)
        if same_guild or allow_cross_guild:
            return bot_cached, channel_id, same_guild

    fetchers = [
        getattr(guild, "fetch_channel", None),
        getattr(bot, "fetch_channel", None),
    ]
    for fetcher in fetchers:
        if not callable(fetcher):
            continue
        try:
            fetched = await fetcher(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            continue
        except Exception:
            continue
        same_guild = _same_guild(fetched)
        if same_guild or allow_cross_guild:
            return fetched, channel_id, same_guild

    return None, channel_id, False


def _button_style_from_color(value: str) -> discord.ButtonStyle:
    key = str(value or "").strip().lower()
    mapping = {
        "green": discord.ButtonStyle.green,
        "blurple": discord.ButtonStyle.blurple,
        "red": discord.ButtonStyle.red,
        "gray": discord.ButtonStyle.gray,
    }
    return mapping.get(key, discord.ButtonStyle.blurple)


def _normalize_button_emoji(value: str | None):
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.lower() in {"none", "null", "nil", "undefined", "false", "no_emoji", "no-emoji", "-"}:
        return None
    text = raw[:64]

    try:
        parsed = discord.PartialEmoji.from_str(text)
    except Exception:
        parsed = None

    if parsed and getattr(parsed, "id", None):
        parsed_name = str(getattr(parsed, "name", "") or "emoji")
        if not _CUSTOM_EMOJI_NAME_RE.fullmatch(parsed_name):
            parsed_name = "emoji"
        return discord.PartialEmoji(
            name=parsed_name,
            id=int(parsed.id),
            animated=bool(getattr(parsed, "animated", False)),
        )

    if text.startswith(":") and text.endswith(":"):
        return None
    if any(char.isspace() for char in text):
        return None
    if len(text) > 16:
        return None
    return text


def _component_has_custom_id(component, custom_id: str) -> bool:
    if not custom_id:
        return False
    try:
        if str(getattr(component, "custom_id", "") or "") == custom_id:
            return True
    except Exception:
        pass
    for attr_name in ("children", "components", "items"):
        try:
            children = getattr(component, attr_name, None)
        except Exception:
            children = None
        if not children:
            continue
        if isinstance(children, (list, tuple)):
            for child in children:
                if _component_has_custom_id(child, custom_id):
                    return True
    return False


def _message_has_custom_id(message, custom_id: str) -> bool:
    if not message or not custom_id:
        return False
    try:
        components = getattr(message, "components", None) or []
    except Exception:
        components = []
    for component in components:
        if _component_has_custom_id(component, custom_id):
            return True
    return False


async def _find_recent_bot_message_with_custom_id(
    channel,
    *,
    custom_id: str,
    bot_user_id: int | None = None,
    limit: int = 80,
):
    if not channel or not custom_id:
        return None
    try:
        async for item in channel.history(limit=max(1, int(limit or 1))):
            if bot_user_id is not None:
                author_id = getattr(getattr(item, "author", None), "id", None)
                if author_id != bot_user_id:
                    continue
            if _message_has_custom_id(item, custom_id):
                return item
    except Exception:
        return None
    return None


async def _cleanup_duplicate_bot_messages_with_custom_id(
    channel,
    *,
    keep_message_id: int | None,
    custom_id: str,
    bot_user_id: int | None = None,
    limit: int = 120,
):
    if not channel or not custom_id:
        return
    try:
        async for item in channel.history(limit=max(1, int(limit or 1))):
            if keep_message_id and getattr(item, "id", None) == keep_message_id:
                continue
            if bot_user_id is not None:
                author_id = getattr(getattr(item, "author", None), "id", None)
                if author_id != bot_user_id:
                    continue
            if not _message_has_custom_id(item, custom_id):
                continue
            try:
                await item.delete()
            except Exception:
                continue
    except Exception:
        pass


async def _edit_or_resend_v2_message(channel, message, view):
    if message:
        try:
            await message.edit(view=view)
            return message
        except discord.HTTPException as error:
            if "IS_COMPONENTS_V2" not in str(error):
                raise
            try:
                await message.delete()
            except Exception:
                pass
    return await channel.send(view=view)


async def save_transcript_file(
    transcript_bytes: BytesIO,
    creator_id: int,
    guild_id: int,
    channel_id: int,
):
    try:
        transcripts_dir = Path(__file__).resolve().parents[3] / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        transcript_file_id = f"{guild_id}-{channel_id}-{creator_id}.html"
        file_path = transcripts_dir / transcript_file_id
        with open(file_path, "wb") as f:
            f.write(transcript_bytes.read())

        return transcript_file_id
    except Exception as e:
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
        return False


async def delete_channel_callback(
    interaction: discord.Interaction, bot: AutoShardedBot, ticket_data
):
    try:
        async def safe_interaction_reply(message: str):
            try:
                await interaction.edit_original_response(content=message)
                return
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass
            try:
                await interaction.followup.send(content=message, ephemeral=True)
            except Exception:
                pass

        await interaction.response.defer(ephemeral=True, thinking=True)
        ticket_data = await storage.tickets.get(id=ticket_data["id"])
        if not ticket_data:
            return await safe_interaction_reply(f"{bot.emoji.ERROR} Ticket not found")
        if not ticket_data.get("closed", False):
            return await safe_interaction_reply(f"{bot.emoji.ERROR} Ticket is not closed")
        guild_id_str = str(interaction.guild.id)
        ticket_module_id_str = str(ticket_data.get("ticket_module_id", 0))
        ticket_settings = cache.ticket_settings.get(guild_id_str, {})
        support_roles_str = ticket_settings.get(ticket_module_id_str, {}).get(
            "support_roles", "[]"
        )
        support_role_ids = _support_roles(support_roles_str)

        if not await checks.close_ticket_permissions(
            user=interaction.user,
            guild=interaction.guild,
            creator_id=None,
            support_role_ids=support_role_ids,
            notify=False,
        ):
            return await safe_interaction_reply(
                f"{bot.emoji.ERROR} You don't have permission to delete this ticket channel"
            )

        try:
            channel = interaction.guild.get_channel(ticket_data.get("channel_id"))
            if channel:
                await safe_interaction_reply(f"{bot.emoji.SUCCESS} Deleting channel...")
                await channel.delete()
                try:
                    await storage.tickets.update(id=ticket_data["id"], deleted=True)
                except Exception as e:
                    logger.error(f"Error updating ticket: {e}")
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            await safe_interaction_reply(f"{bot.emoji.ERROR} Failed to delete channel")
    except Exception as e:
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")


async def ticket_close_action(
    guild: discord.Guild, ticket_data, bot: AutoShardedBot, closed_by: discord.Member
):
    try:
        if ticket_data.get("closed", False):
            logger.warning(f"Ticket already closed: {ticket_data['id']}")
            return False
        ticket_data = await storage.tickets.update(
            id=ticket_data.get("id"),
            closed=True,
            closed_at=datetime.datetime.utcnow(),
        )
        if ticket_data.get("closed", False) == False:
            logger.warning(f"Error closing ticket: {ticket_data['id']}")
            return False
        try:
            creator = await guild.fetch_member(ticket_data.get("creator_id"))
        except Exception:
            creator = None

        try:
            channel = guild.get_channel(ticket_data.get("channel_id"))
        except Exception:
            channel = None
        if not channel:
            logger.warning(f"Channel not found for ticket: {ticket_data['id']}")
            return False

        transcript_bytes = await chat_exporter.export_chat(bot, guild, channel)

        if channel:
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True),
                }
                ticket_module_id = ticket_data.get("ticket_module_id", 0)
                ticket_settings_data = cache.ticket_settings.get(str(guild.id), {}).get(
                    str(ticket_module_id), {}
                )
                for support_role_id in _support_roles(
                    ticket_settings_data.get("support_roles", "[]")
                ):
                    support_role = guild.get_role(support_role_id)
                    if support_role:
                        overwrites[support_role] = discord.PermissionOverwrite(
                            view_channel=True
                        )
                closed_category_id = ticket_settings_data.get(
                    "closed_ticket_category_id", None
                )

                closed_category = None
                if closed_category_id:
                    closed_category = guild.get_channel(closed_category_id)
                    if closed_category and len(closed_category.channels) >= 50:
                        closed_category = None

                await channel.edit(
                    category=closed_category,
                    overwrites=overwrites,
                    name=channel.name.replace("ticket-", "closed-"),
                    topic=f"Closed by {closed_by.mention if closed_by else 'Unknown'}",
                )
            except Exception as e:
                logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

        transcript_url = None
        if transcript_bytes:
            transcript_file_id = await save_transcript_file(
                transcript_bytes=transcript_bytes,
                creator_id=ticket_data["creator_id"],
                guild_id=ticket_data["guild_id"],
                channel_id=ticket_data["channel_id"],
            )
            if transcript_file_id:
                base_url = str(getattr(bot.BotConfig, "DASHBOARD_BASE_URL", "") or "").rstrip("/")
                if base_url:
                    transcript_url = f"{base_url}/transcripts/{transcript_file_id}"

        try:
            close_markdown = (
                f"## Ticket #{str(ticket_data.get('ticket_id')).zfill(4)} Closed\n"
                f"**{bot.emoji.ID} ID**: `{ticket_data.get('ticket_id')}`\n"
                f"**{bot.emoji.GUILD} Guild**: {guild.name}\n"
                f"**{bot.emoji.USER} Creator**: <@{ticket_data.get('creator_id')}>\n"
                f"**{bot.emoji.CLOSE} Closed By**: {closed_by.mention if closed_by else 'Unknown'}\n"
                f"**{bot.emoji.CREATED} Created At**: <t:{int(ticket_data.get('created_at').timestamp())}:F>\n"
                f"**{bot.emoji.CREATED} Closed At**: <t:{int(ticket_data.get('closed_at').timestamp())}:F>\n"
                f"**{bot.emoji.TOPIC} Topic**: {channel.topic if channel.topic else 'No topic provided'}\n"
                f"**{bot.emoji.CHANNEL} Channel ID**: `{channel.id}`\n"
                f"-# Powered by {bot.user.name}"
            )
            actions = []
            if transcript_url:
                actions.append(
                    discord.ui.Button(
                        label="View Transcript",
                        style=discord.ButtonStyle.link,
                        url=transcript_url,
                        emoji=bot.emoji.TRANSCRIPT,
                    )
                )
            view = _build_layout_with_actions([close_markdown], actions, timeout=None)
            if channel:
                try:
                    await channel.send(view=view)
                except Exception:
                    logger.error("เกิดข้อผิดพลาดในการส่งข้อความปิดทิกเก็ตแจ้งห้อง")
            if creator:
                try:
                    await creator.send(view=view)
                except Exception:
                    logger.error("เกิดข้อผิดพลาดในการส่งข้อความปิดทิกเก็ตไปยังผู้สร้างทิกเก็ต")
        except Exception as e:
            logger.error(f"Error sending ticket closed message to creator: {e}")
        return True
    except Exception as e:
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
        return False


async def close_ticket_callback(interaction: discord.Interaction, bot: AutoShardedBot):
    ticket_data = None
    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
        ticket_data = await storage.tickets.get(
            channel_id=interaction.channel.id,
            close_ticket_message_id=interaction.message.id,
            guild_id=interaction.guild.id,
        )
        if not ticket_data:
            return await interaction.edit_original_response(
                content=f"{bot.emoji.ERROR} Ticket not found"
            )
        if ticket_data.get("closed", False):
            return await interaction.edit_original_response(
                content=f"{bot.emoji.ERROR} Ticket already closed"
            )

        guild_id_str = str(interaction.guild.id)
        ticket_module_id_str = str(ticket_data.get("ticket_module_id", 0))
        ticket_settings = cache.ticket_settings.get(guild_id_str, {})
        support_roles_str = ticket_settings.get(ticket_module_id_str, {}).get(
            "support_roles", "[]"
        )
        support_role_ids = _support_roles(support_roles_str)

        if not await checks.close_ticket_permissions(
            user=interaction.user,
            guild=interaction.guild,
            creator_id=ticket_data.get("creator_id"),
            support_role_ids=support_role_ids,
            notify=False,
        ):
            return await interaction.edit_original_response(
                content=f"{bot.emoji.ERROR} You don't have permission to close this ticket"
            )

        disabled_close_button = discord.ui.Button(
            label="Close Ticket",
            style=discord.ButtonStyle.gray,
            emoji=bot.emoji.CLOSE,
            custom_id="close_ticket",
            disabled=True,
        )
        disabled_close_view = _build_layout_with_actions(
            [
                f"## Ticket #{str(ticket_data.get('ticket_id')).zfill(4)}",
                "-# Close request is being processed...",
            ],
            [disabled_close_button],
            timeout=None,
        )
        await interaction.message.edit(view=disabled_close_view)

        if await ticket_close_action(
            interaction.guild, ticket_data, bot, interaction.user
        ):
            await interaction.message.edit(
                view=_build_layout_with_actions(
                    [
                        f"## Ticket #{str(ticket_data.get('ticket_id')).zfill(4)}",
                        f"{bot.emoji.CLOSE} This ticket has been closed.",
                        f"<@{ticket_data.get('creator_id')}>",
                    ],
                    [],
                    timeout=None,
                ),
            )
            await interaction.edit_original_response(
                content=f"{bot.emoji.SUCCESS} Ticket closed successfully"
            )
            delete_view = discord.ui.LayoutView(timeout=None)
            delete_container = discord.ui.Container()
            delete_container.add_item(
                discord.ui.TextDisplay(
                    f"### {bot.emoji.DELETE} Delete Confirmation\nDo you want to delete the ticket channel?"
                )
            )
            DeleteButton = discord.ui.Button(
                label="Delete Ticket Channel",
                style=discord.ButtonStyle.red,
                emoji=bot.emoji.DELETE,
                custom_id="delete_channel",
            )
            DeleteButton.callback = lambda i: delete_channel_callback(
                i, bot, ticket_data
            )
            delete_row = discord.ui.ActionRow()
            delete_row.add_item(DeleteButton)
            delete_container.add_item(delete_row)
            delete_view.add_item(delete_container)
            await interaction.followup.send(view=delete_view)
        else:
            await interaction.edit_original_response(
                content=f"{bot.emoji.ERROR} Error closing ticket"
            )
    except Exception as e:
        try:
            if ticket_data:
                enabled_close_button = discord.ui.Button(
                    label="Close Ticket",
                    style=discord.ButtonStyle.gray,
                    emoji=bot.emoji.CLOSE,
                    custom_id="close_ticket",
                )
                enabled_close_button.callback = lambda i: close_ticket_callback(i, bot)
                await interaction.message.edit(
                    view=_build_layout_with_actions(
                        [
                            f"## Ticket #{str(ticket_data.get('ticket_id')).zfill(4)}",
                            "Click the button below to close this ticket",
                        ],
                        [enabled_close_button],
                        timeout=None,
                    )
                )
        except Exception:
            pass
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")


async def send_close_ticket_module(ticket_data, bot: AutoShardedBot):
    try:
        guild = bot.get_guild(ticket_data["guild_id"])
        if not guild:
            logger.warning(
                f"Guild not found for close ticket message: {ticket_data['guild_id']}"
            )
            return
        try:
            channel = (
                guild.get_channel(ticket_data.get("channel_id"))
                if ticket_data.get("channel_id")
                else None
            )
        except Exception:
            channel = None
        if not channel:
            if ticket_data.get('channel_id'):
                logger.warning(
                    f"Channel not found for close ticket message: {ticket_data.get('channel_id')}"
                )
            return
        try:
            message = await channel.fetch_message(
                ticket_data.get("close_ticket_message_id", None)
            )
        except Exception:
            message = None
        close_embed_data = _parse_json_field(
            ticket_data.get("close_ticket_message_embed", r"{}"), {}
        )
        close_title = _safe_text(
            close_embed_data.get("title") if isinstance(close_embed_data, dict) else "",
            f"Ticket #{str(ticket_data.get('ticket_id')).zfill(4)}",
        )
        close_description = _safe_text(
            ticket_data.get("close_ticket_message_content")
            or (close_embed_data.get("description") if isinstance(close_embed_data, dict) else ""),
            "Click the button below to close this ticket",
        )

        CloseTicketButton = discord.ui.Button(
            label="Close Ticket",
            style=discord.ButtonStyle.gray,
            emoji=bot.emoji.CLOSE,
            custom_id="close_ticket",
        )
        CloseTicketButton.callback = lambda i: close_ticket_callback(i, bot)
        view = _build_layout_with_actions(
            [f"## {close_title}", close_description],
            [CloseTicketButton],
            timeout=None,
        )

        mention_parts = []
        if ticket_data.get("creator_id"):
            mention_parts.append(f"<@{ticket_data.get('creator_id')}>")

        guild_id_str = str(guild.id)
        ticket_module_id_str = str(ticket_data.get("ticket_module_id", 0))
        ticket_settings = cache.ticket_settings.get(guild_id_str, {})
        support_roles_str = ticket_settings.get(ticket_module_id_str, {}).get(
            "support_roles", "[]"
        )
        support_role_ids = _support_roles(support_roles_str)

        if support_role_ids:
            mention_parts.extend(f"<@&{role_id}>" for role_id in support_role_ids)
        mention_line = " ".join(mention_parts)
        lines = [f"## {close_title}", close_description]
        if mention_line:
            lines.append(mention_line)
        view = _build_layout_with_actions(
            lines,
            [CloseTicketButton],
            timeout=None,
        )

        message = await _edit_or_resend_v2_message(channel, message, view)
        if message and message.id != ticket_data.get("close_ticket_message_id"):
            await storage.tickets.update(
                id=ticket_data["id"], close_ticket_message_id=message.id
            )
    except Exception as e:
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")


create_ticket_timeout = {}  # {guild_id: {user_id: datetime.datetime}}


async def create_ticket_callback(interaction: discord.Interaction, bot: AutoShardedBot):
    global create_ticket_timeout
    try:
        if interaction.guild.id not in create_ticket_timeout:
            create_ticket_timeout[interaction.guild.id] = {}
        if interaction.user.id in create_ticket_timeout[interaction.guild.id]:
            if (
                datetime.datetime.utcnow()
                - create_ticket_timeout[interaction.guild.id][interaction.user.id]
            ).total_seconds() < 10:
                return await interaction.response.send_message(
                    content=f"{bot.emoji.ERROR} You are creating tickets too fast",
                    ephemeral=True,
                    delete_after=10,
                )
        create_ticket_timeout[interaction.guild.id][
            interaction.user.id
        ] = datetime.datetime.utcnow()
        ticket_settings_data = cache.ticket_settings.get(str(interaction.guild.id), {})
        if not ticket_settings_data:
            return await interaction.response.send_message(
                content=f"{bot.emoji.ERROR} Ticket module is not **Setup** in this server",
                ephemeral=True,
                delete_after=10,
            )
        if len(interaction.guild.channels) >= 500:
            return await interaction.response.send_message(
                content=f"{bot.emoji.ERROR} คุณไม่สามารถเปิดตั๋วได้ เพราะเซิร์ฟเวอร์ถึงขีดจำกัดสูงสุด `500` ห้องแล้ว",
                ephemeral=True,
                delete_after=10,
            )
        ticket_module_id = None
        for ticket_module in ticket_settings_data.values():
            panel_channel_id = _safe_int(ticket_module.get("ticket_panel_channel_id"), 0)
            panel_message_id = _safe_int(ticket_module.get("ticket_panel_message_id"), 0)
            if (
                panel_channel_id == interaction.channel.id
                and panel_message_id == interaction.message.id
            ):
                ticket_module_id = ticket_module["ticket_module_id"]
                break
        if not ticket_module_id:
            return await interaction.response.send_message(
                content=f"{bot.emoji.ERROR} Ticket module is not **Setup** in this server",
                ephemeral=True,
                delete_after=10,
            )
        ticket_module_data = ticket_settings_data.get(str(ticket_module_id), {})
        if not ticket_module_data:
            return await interaction.response.send_message(
                content=f"{bot.emoji.ERROR} Ticket module is not **Setup** in this server",
                ephemeral=True,
                delete_after=10,
            )

        if ticket_module_data.get("enabled", False) == False:
            return await interaction.response.send_message(
                content=f"{bot.emoji.DISABLED_BUNDLE} Ticket module is **Disabled** in this server",
                ephemeral=True,
                delete_after=10,
            )

        class SelectTopic(discord.ui.Modal, title="Ticket Info"):
            ticket_topic_field = discord.ui.TextInput(
                placeholder="Why are you opening this ticket?",
                label="Ticket Topic",
                max_length=100,
                style=discord.TextStyle.short,
                required=False,
            )

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    await interaction.response.defer(ephemeral=True, thinking=True)
                    opened_tickets = await storage.tickets.count(
                        ticket_module_id=ticket_module_id,
                        guild_id=interaction.guild.id,
                        creator_id=interaction.user.id,
                        closed=False,
                    )
                    if opened_tickets >= ticket_module_data.get("ticket_limit", 1):
                        return await interaction.edit_original_response(
                            content=f"{bot.emoji.ERROR} คุณไม่สามารถเปิดตั๋วมากกว่า `{ticket_module_data.get('ticket_limit',1)}` ใบพร้อมกันได้"
                        )

                    open_ticket_category = (
                        interaction.guild.get_channel(
                            _safe_int(ticket_module_data.get("open_ticket_category_id"), 0)
                        )
                        if ticket_module_data.get("open_ticket_category_id")
                        else None
                    )

                    category_limited = False
                    if open_ticket_category:
                        if len(open_ticket_category.channels) >= 50:
                            category_limited = True

                    ticket_data = await storage.tickets.insert(
                        ticket_module_id=ticket_module_id,
                        guild_id=interaction.guild.id,
                        creator_id=interaction.user.id,
                        closed=False,
                    )
                    if not ticket_data:
                        return await interaction.edit_original_response(
                            content=f"{bot.emoji.ERROR} Error opening ticket"
                        )

                    overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(
                            view_channel=False
                        ),
                        interaction.user: discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True,
                            read_messages=True,
                            attach_files=True,
                            embed_links=True,
                            add_reactions=True,
                        ),
                    }
                    overwrites[interaction.guild.me] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        read_messages=True,
                        attach_files=True,
                        embed_links=True,
                        add_reactions=True,
                        manage_messages=True,
                        manage_channels=True,
                    )
                    support_roles = _support_roles(
                        ticket_module_data.get("support_roles", r"[]")
                    )
                    for role_id in support_roles:
                        role = interaction.guild.get_role(role_id)
                        if role:
                            overwrites[role] = discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=True,
                                read_message_history=True,
                                read_messages=True,
                                attach_files=True,
                                embed_links=True,
                                add_reactions=True,
                                manage_messages=True,
                            )

                    ticket_channel = await interaction.guild.create_text_channel(
                        name=f"ticket-{str(ticket_data['ticket_id']).zfill(4)}",
                        category=(
                            open_ticket_category
                            if open_ticket_category and not category_limited
                            else None
                        ),
                        topic=(
                            self.ticket_topic_field.value
                            if self.ticket_topic_field.value != ""
                            else "No topic provided"
                        ),
                        overwrites=overwrites,
                    )
                    if not ticket_channel:
                        await storage.tickets.delete(id=ticket_data["id"])
                        return await interaction.edit_original_response(
                            content=f"{bot.emoji.ERROR} Error Creating Ticket Channel"
                        )
                    await storage.tickets.update(
                        id=ticket_data["id"], channel_id=ticket_channel.id
                    )
                    await interaction.edit_original_response(
                        content=f"{bot.emoji.SUCCESS} Ticket opened successfully in {ticket_channel.mention}"
                    )
                    ticket_data = await storage.tickets.get(id=ticket_data["id"])
                    await send_close_ticket_module(ticket_data, bot)
                except Exception as e:
                    logger.error(f"Error in file {__file__}: {traceback.format_exc()}")

        await interaction.response.send_modal(SelectTopic())
    except Exception as e:
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")


async def send_ticket_panel_message(ticket_settings_data, bot: AutoShardedBot):
    try:
        guild = bot.get_guild(ticket_settings_data["guild_id"])
        if not guild:
            logger.warning(
                f"Guild not found for ticket panel message: {ticket_settings_data['guild_id']}"
            )
            return
        channel, panel_channel_id, same_guild = await _resolve_channel_with_fetch(
            bot=bot,
            guild=guild,
            channel_id_raw=ticket_settings_data.get("ticket_panel_channel_id"),
            allow_cross_guild=True,
        )
        if channel and not same_guild:
            resolved_guild_id = getattr(getattr(channel, "guild", None), "id", None)
            logger.warning(
                "Ticket panel guild mismatch detected: "
                f"settings_guild={ticket_settings_data.get('guild_id')} "
                f"resolved_guild={resolved_guild_id} "
                f"channel_id={panel_channel_id}"
            )
            if resolved_guild_id:
                try:
                    updated = await storage.ticket_settings.update(
                        id=ticket_settings_data["id"],
                        guild_id=int(resolved_guild_id),
                        ticket_module_id=int(ticket_settings_data.get("ticket_module_id", 1) or 1),
                    )
                    if updated:
                        ticket_settings_data = updated
                        guild = bot.get_guild(ticket_settings_data["guild_id"]) or guild
                except Exception:
                    logger.error(
                        "Failed to self-heal ticket panel guild mismatch: "
                        f"{traceback.format_exc()}"
                    )
        if not channel:
            if panel_channel_id:
                logger.warning(
                    f"Channel not found for ticket panel message: {panel_channel_id}"
                )
            return
        bot_user_id = getattr(getattr(bot, "user", None), "id", None)
        stored_message_id = (
            _safe_int(ticket_settings_data.get("ticket_panel_message_id", None), 0) or None
        )
        message = None
        if stored_message_id:
            try:
                message = await channel.fetch_message(stored_message_id)
            except Exception:
                message = None
        if not message:
            message = await _find_recent_bot_message_with_custom_id(
                channel,
                custom_id="create_ticket",
                bot_user_id=bot_user_id,
                limit=120,
            )

        panel_embed_data = _parse_json_field(
            ticket_settings_data.get("ticket_panel_message_embed", r"{}"), {}
        )
        panel_title = _safe_text(
            panel_embed_data.get("title") if isinstance(panel_embed_data, dict) else "",
            "Open a ticket",
        )
        panel_description = _safe_text(
            ticket_settings_data.get("ticket_panel_message_content")
            or (panel_embed_data.get("description") if isinstance(panel_embed_data, dict) else ""),
            "Click the button below to open a ticket",
        )
        panel_button_label = _safe_text(
            panel_embed_data.get("button_label") if isinstance(panel_embed_data, dict) else "",
            panel_embed_data.get("button_text") if isinstance(panel_embed_data, dict) else "",
        )[:45] or "Open Ticket"
        panel_button_color = str(
            panel_embed_data.get("button_color") if isinstance(panel_embed_data, dict) else "blurple"
        ).strip().lower()
        panel_button_emoji = str(
            panel_embed_data.get("button_emoji") if isinstance(panel_embed_data, dict) else ""
        ).strip()[:64]
        if not panel_button_emoji:
            panel_button_emoji = str(
                panel_embed_data.get("emoji") if isinstance(panel_embed_data, dict) else ""
            ).strip()[:64]
        if not panel_button_emoji:
            panel_button_emoji = str(getattr(getattr(bot, "emoji", None), "TICKET", "") or "").strip()[:64]
        normalized_panel_button_emoji = _normalize_button_emoji(panel_button_emoji)

        def _build_ticket_panel_view(button_emoji):
            button_kwargs = {
                "label": panel_button_label,
                "style": _button_style_from_color(panel_button_color),
                "custom_id": "create_ticket",
            }
            if button_emoji:
                button_kwargs["emoji"] = button_emoji
            try:
                create_ticket_button = discord.ui.Button(**button_kwargs)
            except Exception:
                button_kwargs.pop("emoji", None)
                create_ticket_button = discord.ui.Button(**button_kwargs)
            create_ticket_button.callback = lambda i: create_ticket_callback(i, bot)
            return _build_layout_with_actions(
                [f"# {panel_title}", panel_description, f"-# Powered by {bot.user.name}"],
                [create_ticket_button],
                timeout=None,
            )

        view = _build_ticket_panel_view(normalized_panel_button_emoji)
        try:
            message = await _edit_or_resend_v2_message(channel, message, view)
        except discord.HTTPException as error:
            if "emoji.name: Invalid emoji" not in str(error):
                raise
            logger.warning(
                "Invalid ticket panel emoji detected; retrying without emoji | "
                f"guild={ticket_settings_data.get('guild_id')} "
                f"module={ticket_settings_data.get('ticket_module_id')} "
                f"emoji_raw={panel_button_emoji!r}"
            )
            view = _build_ticket_panel_view(None)
            message = await _edit_or_resend_v2_message(channel, message, view)
        if message and message.id != stored_message_id:
            await storage.ticket_settings.update(
                id=ticket_settings_data["id"],
                guild_id=ticket_settings_data["guild_id"],
                ticket_module_id=ticket_settings_data["ticket_module_id"],
                ticket_panel_message_id=message.id,
            )
        if message:
            await _cleanup_duplicate_bot_messages_with_custom_id(
                channel,
                keep_message_id=message.id,
                custom_id="create_ticket",
                bot_user_id=bot_user_id,
                limit=160,
            )
    except Exception as e:
        logger.error(f"Error in file {__file__}: {traceback.format_exc()}")
