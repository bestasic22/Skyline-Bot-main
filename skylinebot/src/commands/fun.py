import discord


from discord.ext import commands


from skylinebot.src.checks import checks


from skylinebot.console.logging import logger


from skylinebot.style import color


from skylinebot.utils import pings


from skylinebot.utils import i18n


from skylinebot.workflows import gif


from skylinebot.engine.bot_runtime import AutoShardedBot


from skylinebot.workflows import ui

from skylinebot.utils import fancy_text


import random


import traceback


import asyncio


import time


from typing import Any


import storage.fun_rooms as fun_rooms_db


FUN_ROOM_FIELD_LABELS = {
    "counting_up_channel_id": "ห้องนับเลขไปข้างหน้า",
    "counting_down_channel_id": "ห้องนับเลขถอยหลัง",
    "word_twist_channel_id": "ห้องผวนคำ",
    "guess_word_channel_id": "ห้องเดาคำ",
    "xo_channel_id": "ห้องเล่น XO",
    "chess_channel_id": "ห้องเล่นหมากรุก",
    "slots_channel_id": "ห้องเล่นสล็อต",
    "rps_channel_id": "ห้องเล่นเป่ายิ้งฉุบ",
    "dice_channel_id": "ห้องทอยลูกเต๋า",
    "coinflip_channel_id": "ห้องโยนเหรียญ",
    "number_guess_channel_id": "ห้องทายเลข",
    "word_chain_channel_id": "ห้องต่อคำ",
    "quiz_channel_id": "ห้องควิซ",
}

THAI_GUESS_WORDS = [
    {"answer": "แมว", "mask": "แ_ว", "hint": "สัตว์เลี้ยงร้องเมี้ยว"},
    {"answer": "หมา", "mask": "ห_า", "hint": "สัตว์เลี้ยงเห่า"},
    {"answer": "ปลา", "mask": "ป_า", "hint": "อยู่ในน้ำ"},
    {"answer": "ไก่", "mask": "ไ_่", "hint": "ขันตอนเช้า"},
    {"answer": "บ้าน", "mask": "บ้_น", "hint": "ที่อยู่อาศัย"},
    {"answer": "ท้องฟ้า", "mask": "ท้_ง_้_", "hint": "อยู่เหนือหัวเรา"},
    {"answer": "โรงเรียน", "mask": "โ_งเ_ีย_", "hint": "สถานที่เรียน"},
    {"answer": "ตำรวจ", "mask": "ต_ำ_ว_", "hint": "ผู้รักษากฎหมาย"},
    {"answer": "รถไฟ", "mask": "ร_ไ_", "hint": "วิ่งบนราง"},
    {"answer": "กรุงเทพ", "mask": "ก_ุ_เ_พ", "hint": "เมืองหลวงของไทย"},
    {"answer": "ดวงจันทร์", "mask": "ด_ง_ั_ท_์", "hint": "ขึ้นตอนกลางคืน"},
    {"answer": "มะม่วง", "mask": "ม_ม_่_ง", "hint": "ผลไม้สีเหลือง"},
    {"answer": "แตงโม", "mask": "แ_งโ_", "hint": "ผลไม้ลูกใหญ่สีเขียว"},
    {"answer": "ประเทศไทย", "mask": "ป_ะเ_ศไ_", "hint": "ชื่อประเทศของเรา"},
]

SLOT_SYMBOLS = ["7️⃣", "💎", "⭐", "🍒", "🍋", "🍉", "🍀"]

WORD_CHAIN_SEEDS = [
    "แมว",
    "ปลา",
    "หมา",
    "รถไฟ",
    "โรงเรียน",
    "ตำรวจ",
    "ท้องฟ้า",
    "ประเทศไทย",
]

QUIZ_QUESTIONS = [
    {"question": "เมืองหลวงของประเทศไทยคืออะไร?", "answers": ["กรุงเทพ", "กรุงเทพมหานคร"]},
    {"question": "2 + 2 = ?", "answers": ["4", "สี่"]},
    {"question": "สัตว์อะไรร้องเมี้ยว?", "answers": ["แมว"]},
    {"question": "สีของท้องฟ้ากลางวันคือสีอะไร?", "answers": ["ฟ้า", "สีฟ้า"]},
    {"question": "ผลไม้สีเหลืองที่ปอกเปลือกกินได้ทันทีคืออะไร?", "answers": ["กล้วย"]},
    {"question": "จังหวัดเชียงใหม่อยู่ภาคอะไรของไทย?", "answers": ["ภาคเหนือ", "เหนือ"]},
    {"question": "สัตว์ปีกที่ขันตอนเช้าคืออะไร?", "answers": ["ไก่"]},
]


class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TicTacToeView):
            return
        async with view.move_lock:
            if view.game_over:
                await interaction.response.send_message("เกมนี้จบแล้ว", ephemeral=True)
                return
            if interaction.user.id not in view.player_ids:
                await interaction.response.send_message("เกมนี้ไม่ใช่ของคุณ", ephemeral=True)
                return
            if interaction.user.id != view.current_player.id:
                await interaction.response.send_message("ยังไม่ถึงตาคุณ", ephemeral=True)
                return
            if view.board[self.y][self.x] is not None:
                await interaction.response.send_message("ช่องนี้ถูกเลือกไปแล้ว", ephemeral=True)
                return

            mark = "X" if interaction.user.id == view.player_x.id else "O"
            self.label = mark
            self.style = discord.ButtonStyle.danger if mark == "X" else discord.ButtonStyle.success
            self.disabled = True
            view.board[self.y][self.x] = mark

            winner_mark = view.get_winner()
            if winner_mark is not None:
                winner = view.player_x if winner_mark == "X" else view.player_o
                await view.finish_game(
                    interaction,
                    content=f"จบเกมแล้ว! ผู้ชนะคือ {winner.mention} (`{winner_mark}`)",
                )
                return

            if view.is_draw():
                await view.finish_game(interaction, content="จบเกมแล้ว! เสมอ")
                return

            view.current_player = view.player_o if view.current_player.id == view.player_x.id else view.player_x
            if view.current_player.id == view.bot_member_id:
                view.make_bot_move()
                winner_mark = view.get_winner()
                if winner_mark is not None:
                    winner = view.player_x if winner_mark == "X" else view.player_o
                    await view.finish_game(
                        interaction,
                        content=f"จบเกมแล้ว! ผู้ชนะคือ {winner.mention} (`{winner_mark}`)",
                    )
                    return
                if view.is_draw():
                    await view.finish_game(interaction, content="จบเกมแล้ว! เสมอ")
                    return
                view.current_player = view.player_x if view.player_x.id != view.bot_member_id else view.player_o
                next_mark = "X" if view.current_player.id == view.player_x.id else "O"
                await interaction.response.edit_message(
                    content=f"บอทเดินแล้ว ตาของ {view.current_player.mention} (`{next_mark}`)",
                    view=view,
                )
                return

            next_mark = "X" if view.current_player.id == view.player_x.id else "O"
            await interaction.response.edit_message(
                content=f"ตาของ {view.current_player.mention} (`{next_mark}`)",
                view=view,
            )


class TicTacToeView(discord.ui.View):
    def __init__(self, player_x: discord.Member, player_o: discord.Member, bot_member_id: int | None = None):
        super().__init__(timeout=300)
        self.player_x = player_x
        self.player_o = player_o
        self.current_player: discord.Member = player_x
        self.bot_member_id = int(bot_member_id or 0)
        self.player_ids = {player_x.id, player_o.id}
        self.board: list[list[str | None]] = [[None, None, None] for _ in range(3)]
        self.move_lock = asyncio.Lock()
        self.game_over = False
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def is_draw(self) -> bool:
        return all(cell is not None for row in self.board for cell in row)

    def get_winner(self) -> str | None:
        lines = []
        lines.extend(self.board)
        lines.extend([[self.board[0][i], self.board[1][i], self.board[2][i]] for i in range(3)])
        lines.append([self.board[0][0], self.board[1][1], self.board[2][2]])
        lines.append([self.board[0][2], self.board[1][1], self.board[2][0]])
        for line in lines:
            if line[0] is not None and line[0] == line[1] == line[2]:
                return str(line[0])
        return None

    def _available_cells(self) -> list[tuple[int, int]]:
        cells: list[tuple[int, int]] = []
        for y in range(3):
            for x in range(3):
                if self.board[y][x] is None:
                    cells.append((x, y))
        return cells

    def _winner_for_board(self, board: list[list[str | None]]) -> str | None:
        lines = []
        lines.extend(board)
        lines.extend([[board[0][i], board[1][i], board[2][i]] for i in range(3)])
        lines.append([board[0][0], board[1][1], board[2][2]])
        lines.append([board[0][2], board[1][1], board[2][0]])
        for line in lines:
            if line[0] is not None and line[0] == line[1] == line[2]:
                return str(line[0])
        return None

    def _place_mark(self, x: int, y: int, mark: str):
        self.board[y][x] = mark
        for item in self.children:
            if isinstance(item, TicTacToeButton) and item.x == x and item.y == y:
                item.label = mark
                item.style = discord.ButtonStyle.danger if mark == "X" else discord.ButtonStyle.success
                item.disabled = True
                return

    def _disable_all_buttons(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True

    def make_bot_move(self):
        bot_mark = "X" if self.player_x.id == self.bot_member_id else "O"
        human_mark = "O" if bot_mark == "X" else "X"
        available = self._available_cells()
        if not available:
            return

        for x, y in available:
            temp = [row[:] for row in self.board]
            temp[y][x] = bot_mark
            if self._winner_for_board(temp) == bot_mark:
                self._place_mark(x, y, bot_mark)
                return

        for x, y in available:
            temp = [row[:] for row in self.board]
            temp[y][x] = human_mark
            if self._winner_for_board(temp) == human_mark:
                self._place_mark(x, y, bot_mark)
                return

        if self.board[1][1] is None:
            self._place_mark(1, 1, bot_mark)
            return

        corners = [(0, 0), (2, 0), (0, 2), (2, 2)]
        random.shuffle(corners)
        for x, y in corners:
            if self.board[y][x] is None:
                self._place_mark(x, y, bot_mark)
                return

        x, y = random.choice(available)
        self._place_mark(x, y, bot_mark)

    async def finish_game(self, interaction: discord.Interaction, *, content: str):
        self.game_over = True
        self._disable_all_buttons()
        await interaction.response.edit_message(content=content, view=self)
        self.stop()

    async def on_timeout(self):
        self.game_over = True
        self._disable_all_buttons()
        message = getattr(self, "message", None)
        if message is not None:
            try:
                await message.edit(view=self)
            except Exception:
                pass
        self.stop()

class Fun(commands.Cog):

    def __init__(self, bot):

        self.bot: AutoShardedBot = bot

        class CogInfo:

            name = "Fun"

            category = "Extra"

            description = "Fun commands"

            hidden = False

            emoji = self.bot.emoji.FUN or "🎉"

        self.cog_info = CogInfo
        self._fun_room_cache: dict[str, dict[str, Any]] = {}
        self._counting_state: dict[str, dict[str, int]] = {}
        self._guess_state: dict[str, dict[str, Any]] = {}
        self._number_guess_state: dict[str, dict[str, Any]] = {}
        self._word_chain_state: dict[str, dict[str, Any]] = {}
        self._quiz_state: dict[str, dict[str, Any]] = {}
        self._word_twist_cooldowns: dict[tuple[int, int], float] = {}

    async def _get_gif_url(self, query: str) -> str | None:
        try:
            return await asyncio.to_thread(gif.get_gif, query)
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")
            return None

    async def cog_load(self):
        try:
            rows = await fun_rooms_db.get_all()
            self._fun_room_cache = {str(row.get("guild_id")): row for row in rows if row.get("guild_id")}
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    async def _is_fun_admin(self, ctx: commands.Context) -> bool:
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return False
        if await checks.check_is_owner(ctx, notify=False):
            return True
        if getattr(ctx.author.guild_permissions, "administrator", False):
            return True
        return bool(getattr(ctx.author.guild_permissions, "manage_guild", False))

    async def _get_or_create_room_config(self, guild_id: int) -> dict[str, Any]:
        key = str(guild_id)
        cached = self._fun_room_cache.get(key)
        if cached:
            return cached
        row = await fun_rooms_db.get(guild_id=guild_id)
        if row:
            self._fun_room_cache[key] = row
            return row
        created = await fun_rooms_db.insert(guild_id=guild_id)
        created = created or {"guild_id": guild_id}
        self._fun_room_cache[key] = created
        return created

    async def _set_room_config_field(self, guild_id: int, field_name: str, channel_id: int | None) -> dict[str, Any]:
        config = await self._get_or_create_room_config(guild_id)
        if not config.get("id"):
            refreshed = await fun_rooms_db.get(guild_id=guild_id) or await fun_rooms_db.insert(guild_id=guild_id)
            if refreshed:
                config = refreshed
                self._fun_room_cache[str(guild_id)] = config
        if not config.get("id"):
            updated = dict(config)
            updated[field_name] = channel_id
            self._fun_room_cache[str(guild_id)] = updated
            return updated
        update_payload = {"id": config.get("id"), "guild_id": guild_id, field_name: channel_id}
        updated = await fun_rooms_db.update(**update_payload)
        if not updated:
            updated = dict(config)
            updated[field_name] = channel_id
        self._fun_room_cache[str(guild_id)] = updated
        if field_name == "counting_up_channel_id":
            self._counting_state.setdefault(str(guild_id), {})["up"] = 0
        if field_name == "counting_down_channel_id":
            self._counting_state.setdefault(str(guild_id), {})["down"] = 0
        return updated

    async def _ensure_room_for_command(self, ctx: commands.Context, field_name: str) -> bool:
        if not ctx.guild or not ctx.channel:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์")
            return False
        config = await self._get_or_create_room_config(ctx.guild.id)
        channel_id = int(config.get(field_name) or 0)
        if channel_id <= 0:
            return True
        if ctx.channel.id == channel_id:
            return True
        room = ctx.guild.get_channel(channel_id)
        label = room.mention if room else f"`{channel_id}`"
        await ctx.send(f"ใช้คำสั่งนี้ได้เฉพาะในห้อง {label}", delete_after=8)
        return False

    def _parse_int_message(self, content: str) -> int | None:
        raw = str(content or "").strip().replace(",", "")
        if not raw:
            return None
        if raw.startswith("+"):
            raw = raw[1:]
        if raw.startswith("-"):
            return int(raw) if raw[1:].isdigit() else None
        return int(raw) if raw.isdigit() else None

    def _thai_word_twist(self, text: str) -> str:
        words = [word for word in str(text or "").split() if word]
        if len(words) < 2:
            return str(text or "").strip()
        first, second = words[0], words[1]
        if not first or not second:
            return str(text or "").strip()
        swapped_first = second[0] + first[1:] if len(first) > 1 else second[0]
        swapped_second = first[0] + second[1:] if len(second) > 1 else first[0]
        words[0] = swapped_second
        words[1] = swapped_first
        return " ".join(words)

    def _format_room_channel(self, guild: discord.Guild, channel_id: Any) -> str:
        parsed = int(channel_id or 0)
        if parsed <= 0:
            return "`ยังไม่ได้ตั้งค่า`"
        channel = guild.get_channel(parsed)
        if channel:
            return channel.mention
        return f"`{parsed}`"

    def _new_guess_puzzle(self) -> dict[str, str]:
        return random.choice(THAI_GUESS_WORDS)

    def _new_quiz_question(self) -> dict[str, Any]:
        return random.choice(QUIZ_QUESTIONS)

    def _normalize_compare_text(self, text: str) -> str:
        cleaned = str(text or "").strip().lower()
        for token in [" ", "\t", "\n", "\r", "-", "_", "ๆ", ".", ",", "!", "?", ":", ";", "“", "”", "\"", "'"]:
            cleaned = cleaned.replace(token, "")
        return cleaned

    def _word_chain_first_char(self, text: str) -> str:
        stripped = str(text or "").strip()
        return stripped[0] if stripped else ""

    def _word_chain_last_char(self, text: str) -> str:
        stripped = str(text or "").strip()
        return stripped[-1] if stripped else ""

    def _chunk_text(self, text: str, limit: int = 1900) -> list[str]:
        safe = str(text or "")
        if len(safe) <= limit:
            return [safe]
        parts: list[str] = []
        remaining = safe
        while remaining:
            if len(remaining) <= limit:
                parts.append(remaining)
                break
            window = remaining[:limit]
            split_at = max(window.rfind("\n"), window.rfind(" "))
            if split_at < int(limit * 0.55):
                split_at = limit
            chunk = remaining[:split_at].rstrip()
            if not chunk:
                chunk = remaining[:limit]
                split_at = limit
            parts.append(chunk)
            remaining = remaining[split_at:].lstrip("\n ")
        return parts

    async def _send_fancy_style_examples(self, ctx: commands.Context):
        rows = fancy_text.list_styles(sample_text="Fancy Fonts สวัสดี 123")
        lines: list[str] = [
            "**รูปแบบอักษรพิเศษที่รองรับ**",
            f"ใช้งาน: `{self.bot.BotConfig.PREFIX}fancy <style> <ข้อความ>`",
            f"ตัวอย่าง: `{self.bot.BotConfig.PREFIX}fancy double_struck Skyline Bot`",
            f"ทุกสไตล์พร้อมกัน: `{self.bot.BotConfig.PREFIX}fancy all Skyline Bot`",
            "",
        ]
        for row in rows:
            style_id = str(row.get("id") or "").strip()
            style_name = str(row.get("name") or "").strip()
            category_name = str(row.get("category_name") or "").strip()
            preview = str(row.get("preview") or "").strip()
            if category_name:
                lines.append(f"`{style_id}` ({style_name}) - {category_name}")
            else:
                lines.append(f"`{style_id}` ({style_name})")
            lines.append(preview)
            lines.append("")
        payload = "\n".join(lines).strip()
        for index, chunk in enumerate(self._chunk_text(payload, limit=1900)):
            if index == 0:
                await ctx.send(chunk)
            else:
                await ctx.send(chunk)

    async def _send_fancy_all_results(self, ctx: commands.Context, text: str):
        rows = fancy_text.convert_all(text)
        lines: list[str] = ["**ผลลัพธ์ทุกสไตล์**", ""]
        for row in rows:
            style_id = str(row.get("id") or "").strip()
            style_name = str(row.get("name") or "").strip()
            category_name = str(row.get("category_name") or "").strip()
            output = str(row.get("text") or "").strip()
            if category_name:
                lines.append(f"`{style_id}` ({style_name}) - {category_name}")
            else:
                lines.append(f"`{style_id}` ({style_name})")
            lines.append(output or "-")
            lines.append("")
        payload = "\n".join(lines).strip()
        for chunk in self._chunk_text(payload, limit=1900):
            await ctx.send(chunk)

    @commands.hybrid_command(
        name="fancy",
        aliases=["font", "fancytext"],
        help="แปลงข้อความเป็นอักษรพิเศษ",
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=12, type=commands.BucketType.user)
    async def fancy(self, ctx: commands.Context, style: str = "double_struck", *, text: str = ""):
        raw_style = str(style or "").strip()
        raw_text = str(text or "").strip()
        lower_style = raw_style.lower()
        if lower_style in {"list", "styles", "help", "examples"} and not raw_text:
            await self._send_fancy_style_examples(ctx)
            return
        if lower_style in {"all", "allstyles", "all_style", "all-styles"} and raw_text:
            await self._send_fancy_all_results(ctx, raw_text)
            return

        style_is_known = fancy_text.is_known_style(raw_style)
        if not raw_text and raw_style and not style_is_known:
            raw_text = raw_style
            raw_style = "double_struck"
            style_is_known = True

        if not raw_text:
            await ctx.send(
                "ใส่ข้อความที่ต้องการแปลงก่อนนะครับ\n"
                f"ตัวอย่าง: `{self.bot.BotConfig.PREFIX}fancy small_caps Skyline Bot`\n"
                f"ดูผลทุกสไตล์: `{self.bot.BotConfig.PREFIX}fancy all Skyline Bot`\n"
                f"ดูรายชื่อสไตล์: `{self.bot.BotConfig.PREFIX}fancy list`"
            )
            return

        resolved_style = fancy_text.resolve_style(raw_style or "double_struck")
        converted = fancy_text.transform_text(raw_text, resolved_style.key)
        header = f"**{resolved_style.label}** (`{resolved_style.key}`)"
        if raw_style and not style_is_known:
            header += f"\nไม่พบ style `{raw_style}` เลยใช้ `double_struck` แทน"
        payload = f"{header}\n{converted}".strip()
        for chunk in self._chunk_text(payload, limit=1900):
            await ctx.send(chunk)

    @commands.hybrid_group(
        name="funroom",
        help="Manage funroom game channels (จัดการห้องเกม Funroom)",
        description="Manage funroom game channels (จัดการห้องเกม Funroom)",
        invoke_without_command=True,
        with_app_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def funroom(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์")
            return
        config = await self._get_or_create_room_config(ctx.guild.id)
        lines = ["**ตั้งค่าห้องกิจกรรมสนุก**"]
        for field, label in FUN_ROOM_FIELD_LABELS.items():
            lines.append(f"- {label}: {self._format_room_channel(ctx.guild, config.get(field))}")
        lines.append("")
        lines.append("ใช้ `/funroom <ชนิด>` เพื่อตั้งห้อง เช่น `/funroom counting_up #channel`")
        lines.append(
            "ชนิดที่รองรับ: counting_up, counting_down, word_twist, guess_word, xo, chess, slots, rps, dice, coinflip, number_guess, word_chain, quiz"
        )
        await ctx.send("\n".join(lines))

    @funroom.command(
        name="counting_up",
        help="Set Counting Up room (ตั้งค่าห้องนับเลขไปข้างหน้า)",
        description="Set Counting Up room (ตั้งค่าห้องนับเลขไปข้างหน้า)",
    )
    async def funroom_counting_up(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "counting_up_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องนับเลขไปข้างหน้าเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="counting_down",
        help="Set Counting Down room (ตั้งค่าห้องนับเลขถอยหลัง)",
        description="Set Counting Down room (ตั้งค่าห้องนับเลขถอยหลัง)",
    )
    async def funroom_counting_down(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "counting_down_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องนับเลขถอยหลังเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="word_twist",
        help="Set Word Twist room (ตั้งค่าห้องผวนคำ)",
        description="Set Word Twist room (ตั้งค่าห้องผวนคำ)",
    )
    async def funroom_word_twist(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "word_twist_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องผวนคำเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="guess_word",
        help="Set Guess Word room (ตั้งค่าห้องเดาคำ)",
        description="Set Guess Word room (ตั้งค่าห้องเดาคำ)",
    )
    async def funroom_guess_word(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "guess_word_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องเดาคำเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="xo",
        help="Set XO room (ตั้งค่าห้องเล่น XO)",
        description="Set XO room (ตั้งค่าห้องเล่น XO)",
    )
    async def funroom_xo(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "xo_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องเล่น XO เป็น {channel.mention} แล้ว")

    @funroom.command(
        name="chess",
        help="Set Chess room (ตั้งค่าห้องเล่นหมากรุก)",
        description="Set Chess room (ตั้งค่าห้องเล่นหมากรุก)",
    )
    async def funroom_chess(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "chess_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องเล่นหมากรุกเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="slots",
        help="Set Slots room (ตั้งค่าห้องเล่นสล็อต)",
        description="Set Slots room (ตั้งค่าห้องเล่นสล็อต)",
    )
    async def funroom_slots(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "slots_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องเล่นสล็อตเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="rps",
        help="Set Rock-Paper-Scissors room (ตั้งค่าห้องเป่ายิ้งฉุบ)",
        description="Set Rock-Paper-Scissors room (ตั้งค่าห้องเป่ายิ้งฉุบ)",
    )
    async def funroom_rps(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "rps_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องเป่ายิ้งฉุบเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="dice",
        help="Set Dice room (ตั้งค่าห้องทอยลูกเต๋า)",
        description="Set Dice room (ตั้งค่าห้องทอยลูกเต๋า)",
    )
    async def funroom_dice(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "dice_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องทอยลูกเต๋าเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="coinflip",
        help="Set Coinflip room (ตั้งค่าห้องโยนเหรียญ)",
        description="Set Coinflip room (ตั้งค่าห้องโยนเหรียญ)",
    )
    async def funroom_coinflip(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "coinflip_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องโยนเหรียญเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="number_guess",
        help="Set Number Guess room (ตั้งค่าห้องทายเลข)",
        description="Set Number Guess room (ตั้งค่าห้องทายเลข)",
    )
    async def funroom_number_guess(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "number_guess_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องทายเลขเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="word_chain",
        help="Set Word Chain room (ตั้งค่าห้องต่อคำ)",
        description="Set Word Chain room (ตั้งค่าห้องต่อคำ)",
    )
    async def funroom_word_chain(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "word_chain_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องต่อคำเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="quiz",
        help="Set Quiz room (ตั้งค่าห้องควิซ)",
        description="Set Quiz room (ตั้งค่าห้องควิซ)",
    )
    async def funroom_quiz(self, ctx: commands.Context, channel: discord.TextChannel):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        await self._set_room_config_field(ctx.guild.id, "quiz_channel_id", channel.id)
        await ctx.send(f"ตั้งค่าห้องควิซเป็น {channel.mention} แล้ว")

    @funroom.command(
        name="clear",
        help="Clear a funroom mapping (ล้างค่าห้องเกม Funroom)",
        description="Clear a funroom mapping (ล้างค่าห้องเกม Funroom)",
    )
    async def funroom_clear(self, ctx: commands.Context, mode: str):
        if not await self._is_fun_admin(ctx):
            await ctx.send("ต้องมีสิทธิ์แอดมินหรือจัดการเซิร์ฟเวอร์")
            return
        mode_map = {
            "counting_up": "counting_up_channel_id",
            "counting_down": "counting_down_channel_id",
            "word_twist": "word_twist_channel_id",
            "guess_word": "guess_word_channel_id",
            "xo": "xo_channel_id",
            "chess": "chess_channel_id",
            "slots": "slots_channel_id",
            "rps": "rps_channel_id",
            "dice": "dice_channel_id",
            "coinflip": "coinflip_channel_id",
            "number_guess": "number_guess_channel_id",
            "word_chain": "word_chain_channel_id",
            "quiz": "quiz_channel_id",
        }
        field_name = mode_map.get(str(mode or "").strip().lower())
        if not field_name:
            await ctx.send(
                "โหมดไม่ถูกต้อง: counting_up, counting_down, word_twist, guess_word, xo, chess, slots, rps, dice, coinflip, number_guess, word_chain, quiz"
            )
            return
        await self._set_room_config_field(ctx.guild.id, field_name, None)
        await ctx.send(f"ล้างค่าห้อง `{mode}` แล้ว")

    @commands.hybrid_command(name="slots", aliases=["slot"], help="เล่นสล็อตสุ่มโชค", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=20, type=commands.BucketType.user)
    async def slot_spin(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "slots_channel_id"):
            return
        spin = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        unique_count = len(set(spin))
        if unique_count == 1:
            result_text = "แจ็กพอต!"
            result_color = color.green
        elif unique_count == 2:
            result_text = "เกือบแตกแจ็กพอต!"
            result_color = color.yellow
        else:
            result_text = "ลองใหม่อีกครั้ง"
            result_color = color.red
        embed = discord.Embed(
            title="สล็อตสนุกๆ",
            description=f"`{' | '.join(spin)}`\n{result_text}",
            color=result_color,
        )
        embed.set_footer(text=f"ผู้เล่น: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="coinflip", aliases=["coin"], help="โยนเหรียญหัวหรือก้อย", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=10, type=commands.BucketType.user)
    async def coinflip(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "coinflip_channel_id"):
            return
        result = random.choice(["หัว", "ก้อย"])
        await ctx.send(f"🪙 ผลการโยนเหรียญ: **{result}**")

    @commands.hybrid_command(name="dice", aliases=["roll"], help="ทอยลูกเต๋า", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=12, type=commands.BucketType.user)
    async def dice(self, ctx: commands.Context, sides: int = 6):
        if not await self._ensure_room_for_command(ctx, "dice_channel_id"):
            return
        max_sides = 1000
        if sides < 2 or sides > max_sides:
            await ctx.send(f"จำนวนหน้าลูกเต๋าต้องอยู่ระหว่าง 2 ถึง {max_sides}")
            return
        result = random.randint(1, sides)
        await ctx.send(f"🎲 {ctx.author.mention} ทอยลูกเต๋า `{sides}` หน้า ได้เลข **{result}**")

    @commands.hybrid_command(
        name="rps", aliases=["เป่ายิ้งฉุบ"], help="เล่นเป่ายิ้งฉุบกับบอท", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=12, type=commands.BucketType.user)
    async def rps(self, ctx: commands.Context, choice: str):
        if not await self._ensure_room_for_command(ctx, "rps_channel_id"):
            return
        normalized = str(choice or "").strip().lower()
        choice_map = {
            "rock": "rock",
            "r": "rock",
            "ค้อน": "rock",
            "paper": "paper",
            "p": "paper",
            "กระดาษ": "paper",
            "scissors": "scissors",
            "s": "scissors",
            "กรรไกร": "scissors",
        }
        user_pick = choice_map.get(normalized)
        if not user_pick:
            await ctx.send("เลือกได้เฉพาะ: `rock`/`paper`/`scissors` หรือ `ค้อน`/`กระดาษ`/`กรรไกร`")
            return
        bot_pick = random.choice(["rock", "paper", "scissors"])
        emoji_map = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        label_map = {"rock": "ค้อน", "paper": "กระดาษ", "scissors": "กรรไกร"}
        if user_pick == bot_pick:
            verdict = "เสมอ!"
        elif (
            (user_pick == "rock" and bot_pick == "scissors")
            or (user_pick == "paper" and bot_pick == "rock")
            or (user_pick == "scissors" and bot_pick == "paper")
        ):
            verdict = "คุณชนะ!"
        else:
            verdict = "บอทชนะ!"
        await ctx.send(
            f"{ctx.author.mention} เลือก {emoji_map[user_pick]} {label_map[user_pick]}\n"
            f"บอทเลือก {emoji_map[bot_pick]} {label_map[bot_pick]}\n"
            f"**{verdict}**"
        )

    @commands.hybrid_command(
        name="xo",
        help="Play XO with a friend or the bot (เล่น XO กับเพื่อนหรือกับบอท)",
        with_app_command=False,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=20, type=commands.BucketType.user)
    async def xo(self, ctx: commands.Context, opponent: discord.Member = None):
        if not await self._ensure_room_for_command(ctx, "xo_channel_id"):
            return
        bot_member = ctx.guild.me
        target = opponent
        if target is None:
            target = bot_member

        if target is None:
            await ctx.send("ไม่พบบอทในกิลด์นี้")
            return
        if target.id == ctx.author.id:
            await ctx.send("เลือกผู้เล่นคนอื่นเพื่อเริ่มเกม")
            return
        if target.bot and target.id != self.bot.user.id:
            await ctx.send("เล่นกับบอทได้เฉพาะบอทตัวนี้เท่านั้น")
            return

        is_vs_bot = bool(target.bot and target.id == self.bot.user.id)
        view = TicTacToeView(
            player_x=ctx.author,
            player_o=target,
            bot_member_id=self.bot.user.id if is_vs_bot else 0,
        )
        await ctx.send(
            content=f"เริ่มเกม XO: {ctx.author.mention} (`X`) vs {target.mention} (`O`)\nตาของ {ctx.author.mention}",
            view=view,
        )

    @commands.hybrid_command(name="chess", help="เริ่มดวลหมากรุก", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=30, type=commands.BucketType.user)
    async def chess(self, ctx: commands.Context, opponent: discord.Member = None):
        if not await self._ensure_room_for_command(ctx, "chess_channel_id"):
            return
        if opponent and opponent.bot:
            await ctx.send("โปรดเลือกคู่แข่งที่ไม่ใช่บอท")
            return
        invite_text = f"กับ {opponent.mention}" if opponent else ""
        embed = discord.Embed(
            title="กระดานหมากรุกพร้อมแล้ว",
            description=(
                f"{ctx.author.mention} เริ่มดวลหมากรุก {invite_text}\n"
                "เปิดห้องเล่นทันที: https://lichess.org/"
            ),
            color=color.random_color(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="guessstart", aliases=["guess_begin"], help="เริ่มเกมเดาคำ", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def guessstart(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "guess_word_channel_id"):
            return
        puzzle = self._new_guess_puzzle()
        guild_key = str(ctx.guild.id)
        self._guess_state[guild_key] = {
            "channel_id": ctx.channel.id,
            "answer": puzzle["answer"],
            "mask": puzzle["mask"],
            "hint": puzzle["hint"],
        }
        await ctx.send(
            f"เริ่มเกมเดาคำแล้ว!\nคำใบ้: `{puzzle['mask']}`\nคำแนะนำ: {puzzle['hint']}\nพิมพ์คำตอบในห้องนี้ได้เลย"
        )

    @commands.hybrid_command(
        name="guessskip", aliases=["guess_next"], help="ข้ามคำปัจจุบันและสุ่มใหม่", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def guessskip(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "guess_word_channel_id"):
            return
        guild_key = str(ctx.guild.id)
        state = self._guess_state.get(guild_key)
        if not state or int(state.get("channel_id") or 0) != ctx.channel.id:
            await ctx.send("ยังไม่มีเกมเดาคำที่กำลังเล่นในห้องนี้")
            return
        old_answer = state.get("answer")
        puzzle = self._new_guess_puzzle()
        self._guess_state[guild_key] = {
            "channel_id": ctx.channel.id,
            "answer": puzzle["answer"],
            "mask": puzzle["mask"],
            "hint": puzzle["hint"],
        }
        await ctx.send(
            f"เฉลยคำเดิม: `{old_answer}`\nคำใหม่: `{puzzle['mask']}`\nคำแนะนำ: {puzzle['hint']}"
        )

    @commands.hybrid_command(
        name="guessstop", aliases=["guess_end"], help="หยุดเกมเดาคำ", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def guessstop(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "guess_word_channel_id"):
            return
        guild_key = str(ctx.guild.id)
        state = self._guess_state.pop(guild_key, None)
        if not state:
            await ctx.send("ยังไม่มีเกมเดาคำที่กำลังเล่น")
            return
        await ctx.send(f"หยุดเกมเดาคำแล้ว (คำล่าสุดคือ `{state.get('answer')}`)")

    @commands.hybrid_command(
        name="numberstart", aliases=["numstart"], help="เริ่มเกมทายเลข", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def numberstart(self, ctx: commands.Context, min_number: int = 1, max_number: int = 100):
        if not await self._ensure_room_for_command(ctx, "number_guess_channel_id"):
            return
        if min_number >= max_number:
            await ctx.send("ช่วงเลขไม่ถูกต้อง (ต้องให้ `min_number < max_number`)")
            return
        if (max_number - min_number) > 100000:
            await ctx.send("ช่วงเลขกว้างเกินไป (สูงสุด 100000)")
            return
        answer = random.randint(min_number, max_number)
        guild_key = str(ctx.guild.id)
        self._number_guess_state[guild_key] = {
            "channel_id": ctx.channel.id,
            "min": min_number,
            "max": max_number,
            "answer": answer,
            "attempts": 0,
        }
        await ctx.send(
            f"เริ่มเกมทายเลขแล้ว! ทายเลขระหว่าง **{min_number} - {max_number}**\n"
            "พิมพ์ตัวเลขในห้องนี้เพื่อทายได้เลย"
        )

    @commands.hybrid_command(
        name="numberskip", aliases=["numskip"], help="ข้ามเลขปัจจุบันแล้วสุ่มใหม่", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def numberskip(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "number_guess_channel_id"):
            return
        guild_key = str(ctx.guild.id)
        state = self._number_guess_state.get(guild_key)
        if not state or int(state.get("channel_id") or 0) != ctx.channel.id:
            await ctx.send("ยังไม่มีเกมทายเลขในห้องนี้")
            return
        old_answer = int(state.get("answer") or 0)
        min_number = int(state.get("min") or 1)
        max_number = int(state.get("max") or 100)
        new_answer = random.randint(min_number, max_number)
        state["answer"] = new_answer
        state["attempts"] = 0
        await ctx.send(
            f"เฉลยเลขเดิม: `{old_answer}`\n"
            f"สุ่มใหม่แล้ว! ทายเลขระหว่าง **{min_number} - {max_number}**"
        )

    @commands.hybrid_command(
        name="numberstop", aliases=["numstop"], help="หยุดเกมทายเลข", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def numberstop(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "number_guess_channel_id"):
            return
        guild_key = str(ctx.guild.id)
        state = self._number_guess_state.pop(guild_key, None)
        if not state:
            await ctx.send("ยังไม่มีเกมทายเลขที่กำลังเล่น")
            return
        await ctx.send(f"หยุดเกมทายเลขแล้ว (เลขล่าสุดคือ `{state.get('answer')}`)")

    @commands.hybrid_command(
        name="wordchainstart", aliases=["chainstart"], help="เริ่มเกมต่อคำ", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def wordchainstart(self, ctx: commands.Context, *, seed: str = None):
        if not await self._ensure_room_for_command(ctx, "word_chain_channel_id"):
            return
        seed_word = str(seed or "").strip() or random.choice(WORD_CHAIN_SEEDS)
        guild_key = str(ctx.guild.id)
        self._word_chain_state[guild_key] = {
            "channel_id": ctx.channel.id,
            "last_word": seed_word,
            "used_words": {self._normalize_compare_text(seed_word)},
        }
        next_char = self._word_chain_last_char(seed_word)
        await ctx.send(
            f"เริ่มเกมต่อคำแล้ว!\nคำเริ่มต้น: **{seed_word}**\n"
            f"คำถัดไปต้องขึ้นต้นด้วย: **{next_char}**"
        )

    @commands.hybrid_command(
        name="wordchainreset", aliases=["chainreset"], help="รีเซ็ตเกมต่อคำ", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def wordchainreset(self, ctx: commands.Context, *, seed: str = None):
        if not await self._ensure_room_for_command(ctx, "word_chain_channel_id"):
            return
        seed_word = str(seed or "").strip() or random.choice(WORD_CHAIN_SEEDS)
        guild_key = str(ctx.guild.id)
        self._word_chain_state[guild_key] = {
            "channel_id": ctx.channel.id,
            "last_word": seed_word,
            "used_words": {self._normalize_compare_text(seed_word)},
        }
        next_char = self._word_chain_last_char(seed_word)
        await ctx.send(
            f"รีเซ็ตเกมต่อคำแล้ว!\nคำเริ่มต้นใหม่: **{seed_word}**\n"
            f"คำถัดไปต้องขึ้นต้นด้วย: **{next_char}**"
        )

    @commands.hybrid_command(
        name="wordchainstop", aliases=["chainstop"], help="หยุดเกมต่อคำ", with_app_command=False
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def wordchainstop(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "word_chain_channel_id"):
            return
        guild_key = str(ctx.guild.id)
        state = self._word_chain_state.pop(guild_key, None)
        if not state:
            await ctx.send("ยังไม่มีเกมต่อคำที่กำลังเล่น")
            return
        await ctx.send(f"หยุดเกมต่อคำแล้ว (คำล่าสุดคือ `{state.get('last_word')}`)")

    @commands.hybrid_command(name="quizstart", help="เริ่มเกมควิซ", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    async def quizstart(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "quiz_channel_id"):
            return
        pick = self._new_quiz_question()
        guild_key = str(ctx.guild.id)
        answers = list(pick.get("answers") or [])
        self._quiz_state[guild_key] = {
            "channel_id": ctx.channel.id,
            "question": str(pick.get("question") or ""),
            "answers": answers,
            "answers_normalized": [self._normalize_compare_text(a) for a in answers],
        }
        await ctx.send(f"🧠 คำถามควิซ:\n{pick.get('question')}")

    @commands.hybrid_command(name="quizskip", help="ข้ามคำถามควิซ", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    async def quizskip(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "quiz_channel_id"):
            return
        guild_key = str(ctx.guild.id)
        state = self._quiz_state.get(guild_key)
        if not state or int(state.get("channel_id") or 0) != ctx.channel.id:
            await ctx.send("ยังไม่มีเกมควิซในห้องนี้")
            return
        old_answer = (state.get("answers") or ["ไม่ระบุ"])[0]
        pick = self._new_quiz_question()
        answers = list(pick.get("answers") or [])
        self._quiz_state[guild_key] = {
            "channel_id": ctx.channel.id,
            "question": str(pick.get("question") or ""),
            "answers": answers,
            "answers_normalized": [self._normalize_compare_text(a) for a in answers],
        }
        await ctx.send(f"เฉลยข้อก่อนหน้า: **{old_answer}**\n🧠 ข้อใหม่:\n{pick.get('question')}")

    @commands.hybrid_command(name="quizstop", help="หยุดเกมควิซ", with_app_command=False)
    @checks.ignore_check()
    @checks.blacklist_check()
    async def quizstop(self, ctx: commands.Context):
        if not await self._ensure_room_for_command(ctx, "quiz_channel_id"):
            return
        guild_key = str(ctx.guild.id)
        state = self._quiz_state.pop(guild_key, None)
        if not state:
            await ctx.send("ยังไม่มีเกมควิซที่กำลังเล่น")
            return
        answer_preview = (state.get("answers") or ["ไม่ระบุ"])[0]
        await ctx.send(f"หยุดเกมควิซแล้ว (คำตอบล่าสุดคือ `{answer_preview}`)")

    @commands.Cog.listener("on_message")
    async def on_fun_rooms_message(self, message: discord.Message):
        try:
            if not message.guild or message.author.bot:
                return
            guild_id = message.guild.id
            config = await self._get_or_create_room_config(guild_id)
            if not config:
                return

            channel_id = message.channel.id
            guild_key = str(guild_id)
            try:
                prefixes = await self.bot.get_prefix(message)
                if isinstance(prefixes, str):
                    prefix_list = [prefixes]
                else:
                    prefix_list = list(prefixes or [])
                if any(str(message.content or "").startswith(prefix) for prefix in prefix_list if prefix):
                    return
            except Exception:
                pass

            counting_up_channel = int(config.get("counting_up_channel_id") or 0)
            counting_down_channel = int(config.get("counting_down_channel_id") or 0)
            word_twist_channel = int(config.get("word_twist_channel_id") or 0)
            guess_word_channel = int(config.get("guess_word_channel_id") or 0)
            number_guess_channel = int(config.get("number_guess_channel_id") or 0)
            word_chain_channel = int(config.get("word_chain_channel_id") or 0)
            quiz_channel = int(config.get("quiz_channel_id") or 0)

            if channel_id == counting_up_channel and counting_up_channel > 0:
                current = self._parse_int_message(message.content)
                state = self._counting_state.setdefault(guild_key, {"up": 0, "down": 0})
                expected = int(state.get("up", 0) or 0) + 1
                if current is None or current != expected:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    warn = await message.channel.send(
                        f"{message.author.mention} ห้องนี้ต้องนับเลขไปข้างหน้าทีละ 1 (เลขถัดไปคือ `{expected}`)"
                    )
                    await asyncio.sleep(4)
                    try:
                        await warn.delete()
                    except Exception:
                        pass
                    return
                state["up"] = current
                return

            if channel_id == counting_down_channel and counting_down_channel > 0:
                current = self._parse_int_message(message.content)
                state = self._counting_state.setdefault(guild_key, {"up": 0, "down": 0})
                last_down = int(state.get("down", 0) or 0)
                expected = (last_down - 1) if last_down else current
                if current is None or current != expected:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    next_text = f"`{(last_down - 1) if last_down else 'เริ่มด้วยเลขใดก็ได้ 1 ครั้งแรก'}`"
                    warn = await message.channel.send(
                        f"{message.author.mention} ห้องนี้ต้องนับเลขถอยหลังทีละ 1 (เลขที่ต้องส่งคือ {next_text})"
                    )
                    await asyncio.sleep(4)
                    try:
                        await warn.delete()
                    except Exception:
                        pass
                    return
                state["down"] = current
                return

            if channel_id == word_twist_channel and word_twist_channel > 0:
                now_ts = time.time()
                cooldown_key = (guild_id, message.author.id)
                if now_ts - self._word_twist_cooldowns.get(cooldown_key, 0.0) < 3.0:
                    return
                twisted = self._thai_word_twist(message.content)
                if twisted and twisted != message.content.strip():
                    self._word_twist_cooldowns[cooldown_key] = now_ts
                    await message.reply(f"ผวนคำ: `{twisted}`", mention_author=False)
                return

            if channel_id == guess_word_channel and guess_word_channel > 0:
                state = self._guess_state.get(guild_key)
                if not state:
                    return
                if int(state.get("channel_id") or 0) != channel_id:
                    return
                answer = str(state.get("answer") or "").strip().lower()
                guess = str(message.content or "").strip().lower()
                if not answer or not guess:
                    return
                if guess == answer:
                    await message.reply(
                        f"ถูกต้อง! {message.author.mention} ตอบว่า `{state.get('answer')}`",
                        mention_author=False,
                    )
                    puzzle = self._new_guess_puzzle()
                    self._guess_state[guild_key] = {
                        "channel_id": channel_id,
                        "answer": puzzle["answer"],
                        "mask": puzzle["mask"],
                        "hint": puzzle["hint"],
                    }
                    await message.channel.send(f"คำต่อไป: `{puzzle['mask']}`\nคำแนะนำ: {puzzle['hint']}")
                    return

            if channel_id == number_guess_channel and number_guess_channel > 0:
                state = self._number_guess_state.get(guild_key)
                if not state:
                    return
                if int(state.get("channel_id") or 0) != channel_id:
                    return
                current = self._parse_int_message(message.content)
                if current is None:
                    return
                answer = int(state.get("answer") or 0)
                min_number = int(state.get("min") or 1)
                max_number = int(state.get("max") or 100)
                state["attempts"] = int(state.get("attempts") or 0) + 1
                if current == answer:
                    attempts = int(state.get("attempts") or 0)
                    await message.reply(
                        f"ถูกต้อง! คำตอบคือ `{answer}` (ใช้ไป {attempts} ครั้ง)\n"
                        f"สุ่มเลขใหม่แล้วในช่วง **{min_number}-{max_number}**",
                        mention_author=False,
                    )
                    state["answer"] = random.randint(min_number, max_number)
                    state["attempts"] = 0
                    return
                if current < answer:
                    await message.reply("น้อยไป ลองเลขที่มากกว่านี้", mention_author=False)
                    return
                await message.reply("มากไป ลองเลขที่น้อยกว่านี้", mention_author=False)
                return

            if channel_id == word_chain_channel and word_chain_channel > 0:
                state = self._word_chain_state.get(guild_key)
                if not state:
                    return
                if int(state.get("channel_id") or 0) != channel_id:
                    return
                content = str(message.content or "").strip()
                if not content:
                    return
                candidate = content.split()[0]
                normalized_candidate = self._normalize_compare_text(candidate)
                if not normalized_candidate:
                    return
                used_words = state.get("used_words")
                if not isinstance(used_words, set):
                    used_words = set(used_words or [])
                    state["used_words"] = used_words

                last_word = str(state.get("last_word") or "").strip()
                expected_char = self._word_chain_last_char(last_word)
                first_char = self._word_chain_first_char(candidate)
                if expected_char and first_char != expected_char:
                    await message.reply(
                        f"คำนี้ใช้ไม่ได้ ต้องขึ้นต้นด้วย **{expected_char}**",
                        mention_author=False,
                    )
                    return
                if normalized_candidate in used_words:
                    await message.reply("คำนี้เคยถูกใช้ไปแล้ว ลองคำใหม่", mention_author=False)
                    return
                used_words.add(normalized_candidate)
                state["last_word"] = candidate
                next_char = self._word_chain_last_char(candidate)
                await message.add_reaction("✅")
                await message.channel.send(
                    f"รับคำว่า **{candidate}** แล้ว คำถัดไปต้องขึ้นต้นด้วย **{next_char}**"
                )
                return

            if channel_id == quiz_channel and quiz_channel > 0:
                state = self._quiz_state.get(guild_key)
                if not state:
                    return
                if int(state.get("channel_id") or 0) != channel_id:
                    return
                guess = self._normalize_compare_text(message.content)
                if not guess:
                    return
                answers_normalized = list(state.get("answers_normalized") or [])
                if guess in answers_normalized:
                    answers = list(state.get("answers") or ["ไม่ระบุ"])
                    await message.reply(
                        f"ตอบถูกต้อง! คำตอบคือ **{answers[0]}**",
                        mention_author=False,
                    )
                    pick = self._new_quiz_question()
                    next_answers = list(pick.get("answers") or [])
                    self._quiz_state[guild_key] = {
                        "channel_id": channel_id,
                        "question": str(pick.get("question") or ""),
                        "answers": next_answers,
                        "answers_normalized": [self._normalize_compare_text(a) for a in next_answers],
                    }
                    await message.channel.send(f"🧠 ข้อต่อไป:\n{pick.get('question')}")
                    return
        except Exception:
            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="slap", help="👋 ตบคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def slap(self, ctx: commands.Context, user: discord.User = None):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        if not user:

            user = ctx.author

        # get slap gif

        image_url = await self._get_gif_url("slapping")

        target = user.name if user.id != ctx.author.id else i18n.tr("fun_self_target", guild_id)

        embed = discord.Embed(
            title=i18n.tr("fun_slap_title", guild_id, user=ctx.author.name, target=target),
            color=color.random_color(),
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="hug", help="🤗 กอดคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def hug(self, ctx: commands.Context, user: discord.User = None):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        if not user:

            user = ctx.author

        # get hug gif

        image_url = await self._get_gif_url("hugging")

        target = user.name if user.id != ctx.author.id else i18n.tr("fun_self_target", guild_id)

        embed = discord.Embed(
            title=i18n.tr("fun_hug_title", guild_id, user=ctx.author.name, target=target),
            color=color.random_color(),
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="kiss", help="💋 จุ๊บคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def kiss(self, ctx: commands.Context, user: discord.User = None):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        if not user:

            user = ctx.author

        # get kiss gif

        image_url = await self._get_gif_url("kissing")

        target = user.name if user.id != ctx.author.id else i18n.tr("fun_self_target", guild_id)

        embed = discord.Embed(
            title=i18n.tr("fun_kiss_title", guild_id, user=ctx.author.name, target=target),
            color=color.random_color(),
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="pat", help="🐾 ลูบหัวคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def pat(self, ctx: commands.Context, user: discord.User = None):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        if not user:

            user = ctx.author

        # get pat gif

        image_url = await self._get_gif_url("patting")

        target = user.name if user.id != ctx.author.id else i18n.tr("fun_self_target", guild_id)

        embed = discord.Embed(
            title=i18n.tr("fun_pat_title", guild_id, user=ctx.author.name, target=target),
            color=color.random_color(),
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="cry", help="😢 ร้องไห้", emoji="😢")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def cry(self, ctx: commands.Context):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        # get cry gif

        image_url = await self._get_gif_url("crying")

        embed = discord.Embed(
            title=i18n.tr("fun_cry_title", guild_id, user=ctx.author.name), color=color.random_color()
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="dance", help="💃 เต้น")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def dance(self, ctx: commands.Context):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        # get dance gif

        image_url = await self._get_gif_url("dancing")

        embed = discord.Embed(
            title=i18n.tr("fun_dance_title", guild_id, user=ctx.author.name), color=color.random_color()
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="laugh", help="😂 หัวเราะ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def laugh(self, ctx: commands.Context):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        # get laugh gif

        image_url = await self._get_gif_url("laughing")

        embed = discord.Embed(
            title=i18n.tr("fun_laugh_title", guild_id, user=ctx.author.name), color=color.random_color()
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="smile", help="😊 ยิ้ม")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def smile(self, ctx: commands.Context):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        # get smile gif

        image_url = await self._get_gif_url("smiling")

        embed = discord.Embed(
            title=i18n.tr("fun_smile_title", guild_id, user=ctx.author.name), color=color.random_color()
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="angry", help="😡 โกรธ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def angry(self, ctx: commands.Context, user: discord.User = None):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        if not user:

            user = ctx.author

        # get angry gif

        image_url = await self._get_gif_url("angry")

        target = user.name if user.id != ctx.author.id else i18n.tr("fun_self_target", guild_id)

        embed = discord.Embed(
            title=i18n.tr("fun_angry_title", guild_id, user=ctx.author.name, target=target),
            color=color.random_color(),
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="confused", help="🤔 สับสน")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def confused(self, ctx: commands.Context):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        # get confused gif

        image_url = await self._get_gif_url("confused")

        embed = discord.Embed(
            title=i18n.tr("fun_confused_title", guild_id, user=ctx.author.name), color=color.random_color()
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="sleep", help="😴 นอน")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def sleep(self, ctx: commands.Context):

        guild_id = getattr(getattr(ctx, "guild", None), "id", None)

        # get sleep gif

        image_url = await self._get_gif_url("sleeping cartoon")

        embed = discord.Embed(
            title=i18n.tr("fun_sleep_title", guild_id, user=ctx.author.name), color=color.random_color()
        )

        embed.set_image(url=image_url)

        embed.set_footer(
            text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    @commands.command(name="gay", help="ทำนายระดับความเกย์ของคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def gay_command(self, ctx: commands.Context, user: discord.Member = None):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not user:

                user = ctx.author

            gayness = random.randint(0, 100)

            if any(user.id == dev.id for dev in self.bot.developers):

                gayness = 0

            elif user.id in [
                # 850031806795219014,
                # 1062994575058276373,
                # 791348920324063273,
                # 224611733032009729
            ]:

                gayness = 100

            embed = discord.Embed(
                description=i18n.tr("fun_gay_desc", guild_id, user=user.name, percent=gayness), color=color.random_color()
            )

            embed.set_author(
                name=i18n.tr("fun_gay_level", guild_id, user=user.name), icon_url=user.display_avatar.url
            )

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="lesbian", help="ทำนายระดับเลสเบียนของคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def lesbian(self, ctx: commands.Context, user: discord.Member = None):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not user:

                user = ctx.author

            lasbian = random.randint(0, 100)

            if any(user.id == dev.id for dev in self.bot.developers):

                lasbian = 0

            elif user.id in [
                # 850031806795219014,
                # 1062994575058276373,
                # 791348920324063273,
                # 224611733032009729
            ]:

                lasbian = 100

            embed = discord.Embed(
                description=i18n.tr("fun_lesbian_desc", guild_id, user=user.name, percent=lasbian),
                color=color.random_color(),
            )

            embed.set_author(
                name=i18n.tr("fun_lesbian_level", guild_id, user=user.name), icon_url=user.display_avatar.url
            )

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="horny", help="ทำนายระดับความหื่นของคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def horny(self, ctx: commands.Context, user: discord.Member = None):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not user:

                user = ctx.author

            horny = random.randint(0, 100)

            if any(user.id == dev.id for dev in self.bot.developers):

                horny = 0

            elif user.id in [
                # 850031806795219014,
                # 1062994575058276373,
                # 791348920324063273,
                # 224611733032009729
            ]:

                horny = 100

            embed = discord.Embed(
                description=i18n.tr("fun_horny_desc", guild_id, user=user.name, percent=horny), color=color.random_color()
            )

            embed.set_author(
                name=i18n.tr("fun_horny_level", guild_id, user=user.name), icon_url=user.display_avatar.url
            )

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="simp", help="ทำนายระดับซิมป์ของคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def simp(self, ctx: commands.Context, user: discord.Member = None):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not user:

                user = ctx.author

            simp = random.randint(0, 100)

            if any(user.id == dev.id for dev in self.bot.developers):

                simp = 0

            elif user.id in [
                # 850031806795219014,
                # 1062994575058276373,
                # 791348920324063273,
                # 224611733032009729
            ]:

                simp = 100

            embed = discord.Embed(
                description=i18n.tr("fun_simp_desc", guild_id, user=user.mention, percent=simp),
                color=color.random_color(),
            )

            embed.set_author(
                name=i18n.tr("fun_simp_level", guild_id, user=user.name), icon_url=user.display_avatar.url
            )

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="iq", help="ทำนายระดับไอคิวของคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def iq(self, ctx: commands.Context, user: discord.Member = None):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not user:

                user = ctx.author

            iq = random.randint(0, 200)

            if any(user.id == dev.id for dev in self.bot.developers):

                iq = 200

            elif user.id in [
                # 850031806795219014,
                # 1062994575058276373,
                # 791348920324063273,
                # 224611733032009729
            ]:

                iq = 0

            embed = discord.Embed(
                description=i18n.tr("fun_iq_desc", guild_id, user=user.mention, iq=iq),
                color=color.random_color(),
            )

            embed.set_author(
                name=i18n.tr("fun_iq_level", guild_id, user=user.name), icon_url=user.display_avatar.url
            )

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="cute", help="ทำนายระดับความน่ารักของคนที่ระบุ")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=30, type=commands.BucketType.user)
    async def cute(self, ctx: commands.Context, user: discord.Member = None):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not user:

                user = ctx.author

            cute = random.randint(0, 100)

            if any(user.id == dev.id for dev in self.bot.developers):

                cute = 100

            elif user.id in [
                # 850031806795219014,
                # 1062994575058276373,
                # 791348920324063273,
                # 224611733032009729
            ]:

                cute = 0

            embed = discord.Embed(
                description=i18n.tr("fun_cute_desc", guild_id, user=user.mention, percent=cute),
                color=color.random_color(),
            )

            embed.set_author(
                name=i18n.tr("fun_cute_level", guild_id, user=user.name), icon_url=user.display_avatar.url
            )

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="fakeban", help="แกล้งแบนผู้ใช้", aliases=["fban"])
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=120, type=commands.BucketType.user)
    async def fakeban(
        self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if user.id == self.bot.user.id:

                return await ctx.send(i18n.tr("fun_fakeban_self", guild_id))

            embed = discord.Embed(
                description=f"{self.bot.emoji.BAN} | Successfully Banned {user.mention} !\nReason: `{reason}`",
                color=color.green,
            )

            embed.set_footer(
                text=i18n.tr("fun_fakeban_footer", guild_id, user=str(ctx.author)), icon_url=ctx.author.display_avatar.url
            )

            embed.set_author(name=i18n.tr("fun_fakeban_author", guild_id), icon_url=user.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="fakekick", help="แกล้งเตะผู้ใช้", aliases=["fkick"])
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=3, per=120, type=commands.BucketType.user)
    async def fakekick(
        self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if user.id == self.bot.user.id:

                return await ctx.send(i18n.tr("fun_fakekick_self", guild_id))

            embed = discord.Embed(
                description=f"{self.bot.emoji.KICK} | Successfully Kicked {user.mention} !\nReason: `{reason}`",
                color=color.green,
            )

            embed.set_footer(
                text=i18n.tr("fun_fakekick_footer", guild_id, user=str(ctx.author)), icon_url=ctx.author.display_avatar.url
            )

            embed.set_author(name=i18n.tr("fun_fakekick_author", guild_id), icon_url=user.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(name="nukeall", help="ล้างทุกห้องในเซิร์ฟเวอร์")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    async def nukeall(self, ctx: commands.Context):

        try:

            # fake nuke all channels

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            embed = discord.Embed(
                description=f"{self.bot.emoji.LOADING} | {i18n.tr('fun_nukeall_loading', guild_id)}",
                color=color.random_color(),
            )

            message = await ctx.send(embed=embed)

            await asyncio.sleep(5)

            embed.description = f"{self.bot.emoji.SUCCESS} | {i18n.tr('fun_nukeall_jk', guild_id)} 😂"

            embed.set_image(
                url="https://cdn.discordapp.com/attachments/1286969360224882688/1287446868623888497/bully-surprise.gif"
            )

            await message.edit(embed=embed)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

    @commands.command(
        name="ship",
        help="ทำนายความเข้ากันได้ของคนสองคน",
        aliases=["compatibility", "romance"],
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=4, per=60, type=commands.BucketType.user)
    async def relation(
        self, ctx: commands.Context, user1: discord.Member, user2: discord.Member = None
    ):

        try:

            guild_id = getattr(getattr(ctx, "guild", None), "id", None)

            if not user2:

                user1, user2 = ctx.author, user1

            # fake relationship percentage

            percentage = random.randint(0, 100)

            if any(
                u.id == dev.id for u in [user1, user2] for dev in self.bot.developers
            ):

                percentage = 0

            embed = discord.Embed(
                description=i18n.tr("fun_ship_desc", guild_id, user1=user1.mention, user2=user2.mention, percent=percentage),
                color=color.random_color(),
            )

            embed.set_author(
                name=i18n.tr("fun_ship_author", guild_id), icon_url=ctx.guild.icon.url
            )

            embed.set_footer(
                text=f"{i18n.tr('requested_by', guild_id)} {ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            try:

                image = ui.create_relation_percentage_banner(
                    user1.display_avatar.url, user2.display_avatar.url, percentage
                )

                file = discord.File(image, filename="relationship.png")

                embed.set_image(url="attachment://relationship.png")

            except Exception as e:

                logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")

                file = None

            await ctx.send(embed=embed, file=file)

        except Exception as e:

            logger.error(f"ข้อผิดพลาด in file {__file__}: {traceback.format_exc()}")





