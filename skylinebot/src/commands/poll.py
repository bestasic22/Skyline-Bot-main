from __future__ import annotations

import datetime
import json
import re
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import storage.dashboard_config as dashboard_config_db
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color


POLL_CONFIG_KEY_PREFIX = "poll_v1_guild_"
POLL_NUMBER_EMOJIS = [
    "\u0031\ufe0f\u20e3",
    "\u0032\ufe0f\u20e3",
    "\u0033\ufe0f\u20e3",
    "\u0034\ufe0f\u20e3",
    "\u0035\ufe0f\u20e3",
    "\u0036\ufe0f\u20e3",
    "\u0037\ufe0f\u20e3",
    "\u0038\ufe0f\u20e3",
    "\u0039\ufe0f\u20e3",
    "\U0001F51F",
]
MAX_POLL_OPTIONS = 10
MIN_POLL_OPTIONS = 2
MAX_QUESTION_LENGTH = 240
MAX_OPTION_LENGTH = 90

_MESSAGE_LINK_RE = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(?P<guild>\d+)/(?P<channel>\d+)/(?P<message>\d+)",
    re.IGNORECASE,
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


class Poll(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot

        class CogInfo:
            name = "Poll"
            category = "Main"
            description = "Poll commands"
            hidden = False
            emoji = "\U0001F4CA"

        self.cog_info = CogInfo

    @staticmethod
    def _config_key(guild_id: int, message_id: int) -> str:
        return f"{POLL_CONFIG_KEY_PREFIX}{int(guild_id)}_message_{int(message_id)}"

    @staticmethod
    def _normalize_record(payload: dict[str, Any] | None) -> dict[str, Any]:
        src = payload if isinstance(payload, dict) else {}
        options: list[str] = []
        raw_options = src.get("options")
        if isinstance(raw_options, list):
            for item in raw_options[:MAX_POLL_OPTIONS]:
                text = str(item or "").strip()[:MAX_OPTION_LENGTH]
                if text:
                    options.append(text)

        snapshot_counts: list[int] = []
        raw_snapshot = src.get("snapshot_counts")
        if isinstance(raw_snapshot, list):
            for idx in range(min(len(options), len(raw_snapshot), MAX_POLL_OPTIONS)):
                snapshot_counts.append(max(0, _safe_int(raw_snapshot[idx], 0)))

        status = str(src.get("status") or "open").strip().lower()
        if status not in {"open", "closed"}:
            status = "open"

        out = {
            "guild_id": max(0, _safe_int(src.get("guild_id"), 0)),
            "channel_id": max(0, _safe_int(src.get("channel_id"), 0)),
            "message_id": max(0, _safe_int(src.get("message_id"), 0)),
            "creator_id": max(0, _safe_int(src.get("creator_id"), 0)),
            "question": str(src.get("question") or "").strip()[:MAX_QUESTION_LENGTH],
            "options": options,
            "allow_multi": bool(src.get("allow_multi", True)),
            "status": status,
            "created_at": str(src.get("created_at") or "").strip()[:50],
            "closed_at": str(src.get("closed_at") or "").strip()[:50],
            "closed_by": max(0, _safe_int(src.get("closed_by"), 0)),
            "snapshot_counts": snapshot_counts,
        }
        return out

    async def _load_record(self, guild_id: int, message_id: int) -> dict[str, Any] | None:
        row = await dashboard_config_db.get(config_key=self._config_key(guild_id, message_id))
        if not row:
            return None
        raw = str(row.get("config_value") or "").strip()
        if not raw:
            return None
        try:
            decoded = json.loads(raw)
        except Exception:
            return None
        if not isinstance(decoded, dict):
            return None
        normalized = self._normalize_record(decoded)
        if normalized.get("message_id", 0) <= 0:
            return None
        return normalized

    async def _save_record(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_record(record)
        config_key = self._config_key(normalized["guild_id"], normalized["message_id"])
        encoded = json.dumps(normalized, ensure_ascii=False)
        writer = getattr(dashboard_config_db, "set_config_value", None)
        if callable(writer):
            await writer(config_key=config_key, config_value=encoded)
        else:
            row = await dashboard_config_db.get(config_key=config_key)
            if row and row.get("id"):
                await dashboard_config_db.update(id=row["id"], config_key=config_key, config_value=encoded)
            else:
                await dashboard_config_db.insert(config_key=config_key, config_value=encoded)
        return normalized

    @staticmethod
    def _parse_options(raw: str) -> list[str]:
        text = str(raw or "").strip()
        if not text:
            return []
        if "|" in text:
            parts = text.split("|")
        elif "\n" in text:
            parts = text.splitlines()
        else:
            parts = text.split(",")
        out: list[str] = []
        seen: set[str] = set()
        for item in parts:
            option = str(item or "").strip()[:MAX_OPTION_LENGTH]
            if not option:
                continue
            key = option.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(option)
            if len(out) >= MAX_POLL_OPTIONS:
                break
        return out

    @staticmethod
    def _extract_target_ids(target: str, fallback_channel_id: int) -> tuple[int, int]:
        text = str(target or "").strip()
        if not text:
            return int(fallback_channel_id), 0

        match = _MESSAGE_LINK_RE.search(text)
        if match:
            return _safe_int(match.group("channel"), 0), _safe_int(match.group("message"), 0)

        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            return int(fallback_channel_id), _safe_int(digits, 0)

        return int(fallback_channel_id), 0

    @staticmethod
    def _count_votes_from_message(message: discord.Message, option_count: int) -> list[int]:
        counts = [0] * max(0, min(option_count, MAX_POLL_OPTIONS))
        reaction_map = {str(item.emoji): item for item in (message.reactions or [])}
        for idx, emoji in enumerate(POLL_NUMBER_EMOJIS[: len(counts)]):
            reaction = reaction_map.get(emoji)
            if reaction is None:
                continue
            # Bot adds one reaction for each option at creation time.
            bot_seed = 1 if reaction.me else 0
            counts[idx] = max(0, int(reaction.count) - bot_seed)
        return counts

    @staticmethod
    def _bar(count: int, total: int, width: int = 12) -> str:
        if total <= 0:
            return "[" + ("-" * width) + "]"
        ratio = max(0.0, min(1.0, float(count) / float(total)))
        filled = int(round(ratio * width))
        filled = max(0, min(width, filled))
        return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"

    @staticmethod
    async def _fetch_message_from_guild(
        guild: discord.Guild, channel_id: int, message_id: int
    ) -> discord.Message | None:
        if channel_id <= 0 or message_id <= 0:
            return None
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                fetched = await guild.fetch_channel(channel_id)
                channel = fetched
            except Exception:
                channel = None
        if channel is None or not hasattr(channel, "fetch_message"):
            return None
        try:
            return await channel.fetch_message(message_id)
        except Exception:
            return None

    @staticmethod
    def _build_poll_embed(record: dict[str, Any], *, counts: list[int] | None = None) -> discord.Embed:
        is_closed = str(record.get("status") or "open").strip().lower() == "closed"
        options = list(record.get("options") or [])
        final_counts = list(counts or [])
        if len(final_counts) < len(options):
            final_counts.extend([0] * (len(options) - len(final_counts)))
        final_counts = final_counts[: len(options)]
        total_votes = sum(final_counts)

        embed = discord.Embed(
            title=("Poll (Closed)" if is_closed else "Poll"),
            description=f"**{record.get('question') or '-'}**",
            color=(color.red if is_closed else color.blue),
        )

        if options:
            for idx, option in enumerate(options):
                emoji = POLL_NUMBER_EMOJIS[idx]
                count = final_counts[idx] if idx < len(final_counts) else 0
                if is_closed:
                    percent = (float(count) / float(total_votes) * 100.0) if total_votes > 0 else 0.0
                    value = f"{count} vote(s) | {percent:.1f}% {Poll._bar(count, total_votes)}"
                else:
                    value = "React below to vote."
                embed.add_field(name=f"{emoji} {option}", value=value, inline=False)
        else:
            embed.add_field(name="No options", value="This poll has no valid options.", inline=False)

        creator_id = _safe_int(record.get("creator_id"), 0)
        if is_closed:
            closed_by = _safe_int(record.get("closed_by"), 0)
            footer = f"Poll ID: {record.get('message_id')} | Created by {creator_id} | Closed by {closed_by}"
        else:
            multi = "On" if bool(record.get("allow_multi", True)) else "Off"
            footer = f"Poll ID: {record.get('message_id')} | Created by {creator_id} | Multi-vote: {multi}"
        embed.set_footer(text=footer)

        return embed

    @commands.hybrid_group(
        name="poll",
        with_app_command=True,
        help="สร้างและจัดการโพล",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def poll_group(self, ctx: commands.Context):
        await ctx.send(
            "Poll commands:\n"
            "`/poll create <question> <options>`\n"
            "`/poll results <message_id_or_link>`\n"
            "`/poll close <message_id_or_link>`\n\n"
            "Options format: split choices with `|` (recommended), newline, or comma.\n"
            "Example: `Yes | No | Maybe`"
        )

    @poll_group.command(name="create", help="สร้างแบบสำรวจที่มีหลายตัวเลือก")
    @app_commands.describe(
        question="Poll question",
        options="Choices separated with | (example: Yes | No | Maybe)",
        allow_multi="Allow users to vote for multiple options",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def poll_create(self, ctx: commands.Context, question: str, options: str, allow_multi: bool = True):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")

        clean_question = str(question or "").strip()[:MAX_QUESTION_LENGTH]
        if not clean_question:
            return await ctx.send("Question cannot be empty.")

        parsed_options = self._parse_options(options)
        if len(parsed_options) < MIN_POLL_OPTIONS:
            return await ctx.send("You need at least 2 options. Example: `Yes | No`")
        if len(parsed_options) > MAX_POLL_OPTIONS:
            parsed_options = parsed_options[:MAX_POLL_OPTIONS]

        record: dict[str, Any] = {
            "guild_id": int(ctx.guild.id),
            "channel_id": int(ctx.channel.id) if ctx.channel else 0,
            "message_id": 0,
            "creator_id": int(ctx.author.id),
            "question": clean_question,
            "options": parsed_options,
            "allow_multi": bool(allow_multi),
            "status": "open",
            "created_at": _utc_now_iso(),
            "closed_at": "",
            "closed_by": 0,
            "snapshot_counts": [],
        }

        poll_message = await ctx.send(embed=self._build_poll_embed(record))
        record["message_id"] = int(poll_message.id)
        record = await self._save_record(record)

        reaction_added = 0
        for idx in range(len(parsed_options)):
            try:
                await poll_message.add_reaction(POLL_NUMBER_EMOJIS[idx])
                reaction_added += 1
            except Exception:
                break

        # Update footer with final Poll ID after message creation.
        try:
            await poll_message.edit(embed=self._build_poll_embed(record))
        except Exception:
            pass

        if reaction_added < len(parsed_options):
            await ctx.send(
                "Poll created, but I couldn't add all reaction choices. "
                "Please check `Add Reactions` permission for the bot."
            )

    @poll_group.command(name="results", help="แสดงผลการสำรวจความคิดเห็นในปัจจุบันหรือครั้งสุดท้าย")
    @app_commands.describe(target="Poll message ID or Discord message link")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=20, type=commands.BucketType.user)
    async def poll_results(self, ctx: commands.Context, target: str):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")

        fallback_channel_id = int(ctx.channel.id) if ctx.channel else 0
        channel_id, message_id = self._extract_target_ids(target, fallback_channel_id)
        if message_id <= 0:
            return await ctx.send("Invalid target. Please provide a valid message ID or message link.")

        record = await self._load_record(ctx.guild.id, message_id)
        if record is None:
            return await ctx.send("Poll not found in this server.")

        channel_id = channel_id or _safe_int(record.get("channel_id"), 0)
        poll_message = await self._fetch_message_from_guild(ctx.guild, channel_id, message_id)

        if str(record.get("status")).lower() == "closed" and isinstance(record.get("snapshot_counts"), list):
            counts = [max(0, _safe_int(item, 0)) for item in list(record.get("snapshot_counts", []))]
        elif poll_message is not None:
            counts = self._count_votes_from_message(poll_message, len(list(record.get("options") or [])))
        else:
            counts = [0] * len(list(record.get("options") or []))

        total_votes = sum(counts)
        embed = discord.Embed(
            title="ผลการสำรวจความคิดเห็น",
            description=f"**{record.get('question') or '-'}**",
            color=color.green,
        )
        options = list(record.get("options") or [])
        if not options:
            embed.add_field(name="No options", value="This poll has no options.", inline=False)
        else:
            for idx, option in enumerate(options):
                count = counts[idx] if idx < len(counts) else 0
                percent = (float(count) / float(total_votes) * 100.0) if total_votes > 0 else 0.0
                emoji = POLL_NUMBER_EMOJIS[idx]
                embed.add_field(
                    name=f"{emoji} {option}",
                    value=f"{count} vote(s) | {percent:.1f}% {self._bar(count, total_votes)}",
                    inline=False,
                )
        embed.set_footer(
            text=f"Total votes: {total_votes} | Status: {str(record.get('status') or 'open').upper()} | Poll ID: {message_id}"
        )
        await ctx.send(embed=embed)

    @poll_group.command(name="close", help="ปิดการสำรวจความคิดเห็นและล็อคผลรวมการโหวต")
    @app_commands.describe(target="Poll message ID or Discord message link")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def poll_close(self, ctx: commands.Context, target: str):
        if ctx.guild is None:
            return await ctx.send("This command can only be used in a server.")

        fallback_channel_id = int(ctx.channel.id) if ctx.channel else 0
        channel_id, message_id = self._extract_target_ids(target, fallback_channel_id)
        if message_id <= 0:
            return await ctx.send("Invalid target. Please provide a valid message ID or message link.")

        record = await self._load_record(ctx.guild.id, message_id)
        if record is None:
            return await ctx.send("Poll not found in this server.")

        creator_id = _safe_int(record.get("creator_id"), 0)
        is_creator = int(ctx.author.id) == creator_id
        is_moderator = bool(
            getattr(ctx.author.guild_permissions, "administrator", False)
            or getattr(ctx.author.guild_permissions, "manage_messages", False)
            or getattr(ctx.author.guild_permissions, "manage_guild", False)
        )
        if not (is_creator or is_moderator):
            return await ctx.send("Only the poll creator or moderators can close this poll.")

        if str(record.get("status")).lower() == "closed":
            return await ctx.send("This poll is already closed.")

        channel_id = channel_id or _safe_int(record.get("channel_id"), 0)
        poll_message = await self._fetch_message_from_guild(ctx.guild, channel_id, message_id)
        if poll_message is not None:
            counts = self._count_votes_from_message(poll_message, len(list(record.get("options") or [])))
        else:
            counts = [0] * len(list(record.get("options") or []))

        record["status"] = "closed"
        record["closed_at"] = _utc_now_iso()
        record["closed_by"] = int(ctx.author.id)
        record["snapshot_counts"] = counts
        record = await self._save_record(record)

        if poll_message is not None:
            try:
                await poll_message.edit(embed=self._build_poll_embed(record, counts=counts))
            except Exception:
                pass
            try:
                await poll_message.clear_reactions()
            except Exception:
                pass

        await ctx.send(f"Closed poll `{message_id}` successfully.")
