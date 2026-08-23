import datetime
import io
import os
import re
import sys

import pyfiglet
import pytz
from colorama import Back, Fore, Style, init

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

init(autoreset=True)
timezone = pytz.timezone("Asia/Kolkata")


class Logger:
    def __init__(self) -> None:
        os.makedirs("logs", exist_ok=True)
        stamp = datetime.datetime.now(timezone).strftime("%Y-%m-%d_%H-%M-%S")
        self.logging_file = f"logs/{stamp}.log"
        self.file = open(self.logging_file, "a", encoding="utf-8")
        self._ansi_enabled = self._resolve_ansi_enabled()
        self._debug_enabled = self._resolve_flag("LOG_DEBUG", default=False)
        self._show_cache_update_logs = self._resolve_flag("LOG_CACHE_UPDATES", default=False)
        self._ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
        self.banner()

    def _resolve_ansi_enabled(self) -> bool:
        raw = str(os.getenv("LOG_COLOR", "") or "").strip().lower()
        if raw in {"0", "false", "no", "off"}:
            return False
        if raw in {"1", "true", "yes", "on"}:
            return True
        return True

    def _resolve_flag(self, name: str, *, default: bool) -> bool:
        raw = str(os.getenv(name, "") or "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return bool(default)

    def _with_style(self, text: str, *styles: str) -> str:
        if not self._ansi_enabled:
            return text
        return f"{''.join(styles)}{text}{Style.RESET_ALL}"

    def _strip_ansi(self, text: str) -> str:
        return self._ansi_pattern.sub("", str(text))

    def banner(self):
        try:
            art = pyfiglet.figlet_format("ThunderGod", font="slant")
        except Exception:
            art = "ThunderGod"
        print(f"{Fore.LIGHTWHITE_EX}{Style.BRIGHT}{art}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}+{'-' * 78}+")
        print(
            f"{Fore.CYAN}| "
            f"{Fore.WHITE}{Style.BRIGHT}Name: ThunderGod # 1540935414213517383"
            f"{' ' * 4}"
            f"{Fore.LIGHTBLACK_EX}Credits"
            f"{Fore.WHITE}: Skyline Development"
            f"{' ' * 4}{Fore.CYAN}|"
        )
        print(f"{Fore.CYAN}+{'-' * 78}+{Style.RESET_ALL}\n")

    def startup_summary(self, bot):
        print(f"{Fore.LIGHTBLACK_EX}Session Snapshot")
        print(f"{Fore.BLUE}|- User   {Fore.WHITE}{bot.user} (ID: {bot.user.id})")
        print(f"{Fore.BLUE}|- Guilds {Fore.WHITE}{len(bot.guilds)}")
        print(f"{Fore.BLUE}|- Users  {Fore.WHITE}{sum(g.member_count or 0 for g in bot.guilds)}")
        print(f"{Fore.BLUE}|- Shards {Fore.WHITE}{bot.shard_count}\n")
        
    def web_startup_summary(self, bot):
        print(f"{Fore.LIGHTBLACK_EX}Web Dashboard Snapshot")
        print(f"{Fore.BLUE}|- Host   {Fore.WHITE}{bot.BotConfig.WEB_HOST}")
        print(f"{Fore.BLUE}|- Port   {Fore.WHITE}{bot.BotConfig.WEB_PORT}")
        print(f"{Fore.BLUE}|- URL    {Fore.WHITE}{bot.BotConfig.DASHBOARD_BASE_URL}")


    def _get_timestamp(self):
        return datetime.datetime.now(timezone).strftime("%H:%M:%S")

    def _clean_console_text(self, message) -> str:
        text = str(message)
        try:
            text = text.encode("latin1").decode("utf-8")
        except Exception:
            pass

        mojibake_symbols = {
            b"\xe2\x80\xa2".decode("latin1"): "-",   # bullet
            b"\xe2\x80\xa6".decode("latin1"): "...", # ellipsis
            b"\xe2\x9c\x85".decode("latin1"): "[ok]",
            b"\xe2\x9d\x8c".decode("latin1"): "[x]",
            b"\xf0\x9f\x9a\xa0".decode("latin1"): "[!]",
        }
        replacements = {
            **mojibake_symbols,
            chr(0x2022): "-",                       # •
            chr(0x2026): "...",                    # …
            chr(0x2705): "[ok]",                   # ✅
            chr(0x274C): "[x]",                    # ❌
            f"{chr(0x26A0)}{chr(0xFE0F)}": "[!]",  # ⚠️
            chr(0x26A0): "[!]",                    # ⚠
        }
        for source, target in replacements.items():
            text = text.replace(source, target)

        if any(0x80 <= ord(ch) <= 0x9F for ch in text):
            text = "".join(ch for ch in text if not (0x80 <= ord(ch) <= 0x9F))

        # Keep Unicode text (Thai, emoji, etc.) instead of replacing it with spaces.
        return text

    def _highlight_message(self, message: str, level: str) -> str:
        if not self._ansi_enabled:
            return message
        if "\x1b[" in message:
            # Already colored by caller, keep as-is.
            return message

        text = str(message)

        def paint(pattern: str, color: str) -> None:
            nonlocal text
            text = re.sub(
                pattern,
                lambda m: f"{Style.BRIGHT}{color}{m.group(0)}{Style.RESET_ALL}",
                text,
                flags=re.IGNORECASE,
            )

        # Structure / context
        paint(r"https?://[^\s]+", Fore.LIGHTBLUE_EX)
        paint(r"/[A-Za-z0-9_\-]{2,}", Fore.CYAN)
        paint(r"\[[A-Za-z0-9_.:-]+\]", Fore.LIGHTMAGENTA_EX)

        # Common outcome keywords
        paint(r"\b(error|failed|failure|exception|traceback|timeout|denied|refused|invalid)\b", Fore.RED)
        paint(r"\b(warn|warning|retry|degraded|offline|stale|fallback)\b", Fore.YELLOW)
        paint(r"\b(success|successful|completed|connected|ready|synced|resumed|started|done)\b", Fore.GREEN)

        if str(level).upper() in {"ERROR", "WARNING"}:
            paint(r"\b\d{3}\b", Fore.LIGHTYELLOW_EX)

        return text

    def log(self, message, level="INFO", color=Fore.BLUE):
        message = self._clean_console_text(message)
        timestamp = self._get_timestamp()
        level_key = str(level or "INFO").strip().upper()
        if level_key == "DEBUG" and not self._debug_enabled:
            return
        level_styles = {
            "INFO": (" INFO ", Fore.BLACK, Back.CYAN),
            "DEBUG": (" DEBG ", Fore.BLACK, Back.LIGHTBLACK_EX),
            "SUCCESS": (" PASS ", Fore.BLACK, Back.GREEN),
            "WARNING": (" WARN ", Fore.BLACK, Back.YELLOW),
            "ERROR": (" FAIL ", Fore.WHITE, Back.RED),
            "DATABASE": (" DATA ", Fore.WHITE, Back.MAGENTA),
            "STORAGE": (" DATA ", Fore.WHITE, Back.MAGENTA),
            "SURFACE": (" EDGE ", Fore.BLACK, Back.LIGHTYELLOW_EX),
            "COG": (" SRC  ", Fore.WHITE, Back.BLUE),
            "SYSTEM": (" SYS  ", Fore.BLACK, Back.WHITE),
        }
        label_text, label_fore, label_back = level_styles.get(
            level_key,
            (f" {level_key[:5]:<5}", Fore.WHITE, Back.BLACK),
        )
        level_label = self._with_style(label_text, Style.BRIGHT, label_fore, label_back)
        colored_message = self._highlight_message(message, level_key)
        console_entry = (
            f"{self._with_style(timestamp, Style.DIM, Fore.LIGHTBLACK_EX)} "
            f"{self._with_style('>', Fore.LIGHTBLACK_EX)} "
            f"{level_label} "
            f"{self._with_style('|', Fore.LIGHTBLACK_EX)} "
            f"{self._with_style(colored_message, color)}"
        )
        print(console_entry)
        self.file.write(f"[{timestamp}] [{level_key}] {self._strip_ansi(message)}\n")
        self.file.flush()

    def info(self, message):
        self.log(message, "INFO", Fore.LIGHTCYAN_EX)

    def debug(self, message):
        self.log(message, "DEBUG", Fore.LIGHTBLACK_EX)

    def success(self, message):
        self.log(message, "SUCCESS", Fore.GREEN)

    def warning(self, message):
        self.log(message, "WARNING", Fore.YELLOW)

    def error(self, message):
        self.log(message, "ERROR", Fore.RED)

    def database(self, message):
        if (not self._show_cache_update_logs) and ("cache updated" in str(message or "").lower()):
            return
        self.log(message, "STORAGE", Fore.MAGENTA)

    def storage(self, message):
        self.log(message, "STORAGE", Fore.MAGENTA)

    def surface(self, message):
        self.log(message, "SURFACE", Fore.LIGHTYELLOW_EX)

    def cog(self, message):
        self.log(message, "COG", Fore.LIGHTBLUE_EX)

    def system(self, message):
        self.log(message, "SYSTEM", Fore.LIGHTWHITE_EX)

    def separator(self):
        print(f"{Fore.LIGHTBLACK_EX}{'- ' * 30}")

    def close(self):
        self.file.write(f"Log file closed at {datetime.datetime.now(timezone)}\n")
        self.file.close()


logger = Logger()
