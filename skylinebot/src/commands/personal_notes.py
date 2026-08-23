import datetime
import json
import time
from typing import Any

from discord import app_commands
from discord.ext import commands

import storage.dashboard_config
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks


NOTES_CONFIG_KEY_PREFIX = "notes_v1_user_"
MAX_NOTES_PER_USER = 100
MAX_NOTE_TITLE = 80
MAX_NOTE_CONTENT = 1500


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


class PersonalNotes(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._cache_payload: dict[int, dict[str, Any]] = {}
        self._cache_expire: dict[int, float] = {}
        self._cache_ttl = 90.0

        class CogInfo:
            name = "PersonalNotes"
            category = "Main"
            description = "Personal note commands"
            hidden = False
            emoji = "📝"

        self.cog_info = CogInfo

    @staticmethod
    def _config_key(user_id: int) -> str:
        return f"{NOTES_CONFIG_KEY_PREFIX}{int(user_id)}"

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        return {"next_id": 1, "items": []}

    @classmethod
    def _normalize_payload(cls, payload: dict[str, Any] | None) -> dict[str, Any]:
        src = payload if isinstance(payload, dict) else {}
        out = cls._default_payload()
        out["next_id"] = max(1, _safe_int(src.get("next_id"), 1))
        raw_items = src.get("items")
        items: list[dict[str, Any]] = []
        if isinstance(raw_items, list):
            for row in raw_items:
                if not isinstance(row, dict):
                    continue
                note_id = _safe_int(row.get("id"), 0)
                if note_id <= 0:
                    continue
                title = str(row.get("title") or "").strip()[:MAX_NOTE_TITLE]
                content = str(row.get("content") or "").strip()[:MAX_NOTE_CONTENT]
                if not title or not content:
                    continue
                created_at = str(row.get("created_at") or "").strip()[:40]
                updated_at = str(row.get("updated_at") or "").strip()[:40]
                items.append(
                    {
                        "id": note_id,
                        "title": title,
                        "content": content,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }
                )
        items.sort(key=lambda item: int(item.get("id", 0)))
        if len(items) > MAX_NOTES_PER_USER:
            items = items[-MAX_NOTES_PER_USER:]
        out["items"] = items
        max_id = max((int(item.get("id", 0)) for item in items), default=0)
        out["next_id"] = max(out["next_id"], max_id + 1)
        return out

    @staticmethod
    def _now_iso() -> str:
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

    async def _load_user_notes(self, user_id: int, *, force: bool = False) -> dict[str, Any]:
        user_id_int = int(user_id)
        now_ts = time.monotonic()
        if not force:
            cached = self._cache_payload.get(user_id_int)
            expire_at = float(self._cache_expire.get(user_id_int, 0.0) or 0.0)
            if cached is not None and now_ts < expire_at:
                return cached

        payload = self._default_payload()
        try:
            row = await storage.dashboard_config.get(config_key=self._config_key(user_id_int))
            if row and isinstance(row, dict):
                raw = str(row.get("config_value") or "").strip()
                if raw:
                    decoded = json.loads(raw)
                    if isinstance(decoded, dict):
                        payload = self._normalize_payload(decoded)
        except Exception as error:
            logger.warning(f"Notes load failed for user {user_id_int}: {error}")

        self._cache_payload[user_id_int] = payload
        self._cache_expire[user_id_int] = now_ts + self._cache_ttl
        return payload

    async def _save_user_notes(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        user_id_int = int(user_id)
        normalized = self._normalize_payload(payload)
        encoded = json.dumps(normalized, ensure_ascii=False)
        row = await storage.dashboard_config.get(config_key=self._config_key(user_id_int))
        if row and row.get("id"):
            await storage.dashboard_config.update(
                id=row["id"],
                config_key=self._config_key(user_id_int),
                config_value=encoded,
            )
        else:
            await storage.dashboard_config.insert(
                config_key=self._config_key(user_id_int),
                config_value=encoded,
            )
        self._cache_payload[user_id_int] = normalized
        self._cache_expire[user_id_int] = time.monotonic() + self._cache_ttl
        return normalized

    @staticmethod
    def _find_note(items: list[dict[str, Any]], note_id: int) -> dict[str, Any] | None:
        for row in items:
            if int(row.get("id", 0)) == int(note_id):
                return row
        return None

    @commands.hybrid_group(
        name="notes",
        with_app_command=True,
        help="ผู้จัดการบันทึกส่วนตัว",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def notes_group(self, ctx: commands.Context):
        payload = await self._load_user_notes(ctx.author.id)
        count = len(payload.get("items", []))
        await ctx.send(
            "Notes commands:\n"
            "`/notes add <title> <content>`\n"
            "`/notes list`\n"
            "`/notes view <id>`\n"
            "`/notes edit <id> <content>`\n"
            "`/notes delete <id>`\n"
            "`/notes clear`\n"
            f"Current notes: **{count}/{MAX_NOTES_PER_USER}**"
        )

    @notes_group.command(
        name="add",
        help="Add a personal note (เพิ่มโน้ตส่วนตัว)",
        description="Add a personal note (เพิ่มโน้ตส่วนตัว)",
    )
    @app_commands.describe(title="ชื่อบันทึกย่อ", content="Your note content")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def notes_add(self, ctx: commands.Context, title: str, *, content: str):
        clean_title = str(title or "").strip()[:MAX_NOTE_TITLE]
        clean_content = str(content or "").strip()[:MAX_NOTE_CONTENT]
        if not clean_title:
            return await ctx.send("Title cannot be empty.")
        if not clean_content:
            return await ctx.send("Content cannot be empty.")

        payload = await self._load_user_notes(ctx.author.id, force=True)
        items = list(payload.get("items", []))
        if len(items) >= MAX_NOTES_PER_USER:
            return await ctx.send(f"You reached the limit ({MAX_NOTES_PER_USER} notes). Delete some notes first.")

        note_id = max(1, _safe_int(payload.get("next_id"), 1))
        now_iso = self._now_iso()
        items.append(
            {
                "id": note_id,
                "title": clean_title,
                "content": clean_content,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )
        payload["items"] = items
        payload["next_id"] = note_id + 1
        await self._save_user_notes(ctx.author.id, payload)
        await ctx.send(f"Saved note `#{note_id}`: **{clean_title}**")

    @notes_group.command(
        name="list",
        help="List your personal notes (แสดงรายการโน้ตส่วนตัว)",
        description="List your personal notes (แสดงรายการโน้ตส่วนตัว)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def notes_list(self, ctx: commands.Context):
        payload = await self._load_user_notes(ctx.author.id)
        items = list(payload.get("items", []))
        if not items:
            return await ctx.send("You don't have any notes yet. Use `/notes add`.")

        lines: list[str] = []
        for row in items[-20:]:
            lines.append(f"`#{int(row.get('id', 0))}` **{str(row.get('title') or 'Untitled')}**")
        await ctx.send("Your latest notes:\n" + "\n".join(lines))

    @notes_group.command(
        name="view",
        help="View one note by ID (ดูโน้ตตาม ID)",
        description="View one note by ID (ดูโน้ตตาม ID)",
    )
    @app_commands.describe(note_id="Note ID")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def notes_view(self, ctx: commands.Context, note_id: int):
        payload = await self._load_user_notes(ctx.author.id)
        items = list(payload.get("items", []))
        note = self._find_note(items, note_id)
        if not note:
            return await ctx.send("Note not found.")
        title = str(note.get("title") or "Untitled")
        content = str(note.get("content") or "-")
        updated_at = str(note.get("updated_at") or "-")
        await ctx.send(f"**Note #{note_id} - {title}**\n{content}\n\n`updated: {updated_at}`")

    @notes_group.command(
        name="edit",
        help="Edit a note by ID (แก้ไขโน้ตตาม ID)",
        description="Edit a note by ID (แก้ไขโน้ตตาม ID)",
    )
    @app_commands.describe(note_id="Note ID", content="New content")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def notes_edit(self, ctx: commands.Context, note_id: int, *, content: str):
        clean_content = str(content or "").strip()[:MAX_NOTE_CONTENT]
        if not clean_content:
            return await ctx.send("Content cannot be empty.")
        payload = await self._load_user_notes(ctx.author.id, force=True)
        items = list(payload.get("items", []))
        note = self._find_note(items, note_id)
        if not note:
            return await ctx.send("Note not found.")
        note["content"] = clean_content
        note["updated_at"] = self._now_iso()
        await self._save_user_notes(ctx.author.id, payload)
        await ctx.send(f"Updated note `#{note_id}`.")

    @notes_group.command(
        name="delete",
        help="Delete a note by ID (ลบโน้ตตาม ID)",
        description="Delete a note by ID (ลบโน้ตตาม ID)",
    )
    @app_commands.describe(note_id="Note ID")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def notes_delete(self, ctx: commands.Context, note_id: int):
        payload = await self._load_user_notes(ctx.author.id, force=True)
        items = list(payload.get("items", []))
        before = len(items)
        items = [row for row in items if int(row.get("id", 0)) != int(note_id)]
        if len(items) == before:
            return await ctx.send("Note not found.")
        payload["items"] = items
        await self._save_user_notes(ctx.author.id, payload)
        await ctx.send(f"Deleted note `#{note_id}`.")

    @notes_group.command(
        name="clear",
        help="Delete all personal notes (ลบโน้ตทั้งหมด)",
        description="Delete all personal notes (ลบโน้ตทั้งหมด)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=25, type=commands.BucketType.user)
    async def notes_clear(self, ctx: commands.Context):
        payload = await self._load_user_notes(ctx.author.id, force=True)
        count = len(payload.get("items", []))
        payload["items"] = []
        payload["next_id"] = 1
        await self._save_user_notes(ctx.author.id, payload)
        await ctx.send(f"Cleared all notes ({count} items).")


