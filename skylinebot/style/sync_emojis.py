import os
import re
import time
import base64

import requests
from requests import RequestException
from dotenv import load_dotenv
from colorama import Fore, Style

from skylinebot.console.logging import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()
TOKEN = (os.getenv("TOKEN") or os.getenv("\ufeffTOKEN") or "").strip()
APP_ID = (os.getenv("DISCORD_CLIENT_ID") or os.getenv("\ufeffDISCORD_CLIENT_ID") or "").strip()
REQUEST_TIMEOUT = float(os.getenv("EMOJI_SYNC_TIMEOUT_SECONDS", "20"))
MAX_API_RETRIES = int(os.getenv("EMOJI_SYNC_MAX_API_RETRIES", "6"))
RETRY_BACKOFF_SECONDS = float(os.getenv("EMOJI_SYNC_BACKOFF_SECONDS", "2.5"))


def fetch_emoji_image(emoji_id, animated):
    ext = "gif" if animated else "webp"
    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r.content
        if r.status_code in (301, 302):
            location = r.headers.get("Location")
            if location:
                r2 = requests.get(location, timeout=REQUEST_TIMEOUT)
                if r2.status_code == 200:
                    return r2.content
    except RequestException:
        pass
    return None


def _safe_retry_after_seconds(response) -> float:
    if response is None:
        return 0.0

    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            parsed = float(retry_after)
            if parsed > 0:
                return parsed
        except Exception:
            pass

    try:
        payload = response.json()
        parsed = float(payload.get("retry_after", 0))
        if parsed > 0:
            return parsed
    except Exception:
        pass

    return 0.0


def _rate_limit_scope(response) -> str:
    if response is None:
        return ""
    try:
        return str(response.headers.get("X-RateLimit-Scope", "") or "").strip().lower()
    except Exception:
        return ""


def _discord_api_request(method: str, url: str, headers: dict, **kwargs):
    last_response = None
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )
        except RequestException as err:
            if attempt >= MAX_API_RETRIES:
                raise err

            wait_seconds = min(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)), 60.0)
            logger.warning(
                f"{Fore.YELLOW}EmojiSync network issue:{Style.RESET_ALL} retrying in "
                f"{wait_seconds:.1f}s {Fore.LIGHTBLACK_EX}(attempt {attempt}/{MAX_API_RETRIES}){Style.RESET_ALL}"
            )
            time.sleep(wait_seconds)
            continue

        last_response = response

        if response.status_code == 429:
            # Discord docs note emoji routes may use special/shared limits.
            # For shared limits, retry loops usually don't help and only delay startup.
            if _rate_limit_scope(response) == "shared":
                return response

        if response.status_code == 429 and attempt < MAX_API_RETRIES:
            retry_after = _safe_retry_after_seconds(response)
            wait_seconds = retry_after if retry_after > 0 else min(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)), 60.0)
            logger.warning(
                f"{Fore.YELLOW}EmojiSync rate limited:{Style.RESET_ALL} waiting {wait_seconds:.1f}s before retry "
                f"{Fore.LIGHTBLACK_EX}(attempt {attempt}/{MAX_API_RETRIES}){Style.RESET_ALL}"
            )
            time.sleep(wait_seconds)
            continue

        if response.status_code >= 500 and attempt < MAX_API_RETRIES:
            wait_seconds = min(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)), 60.0)
            logger.warning(
                f"{Fore.YELLOW}EmojiSync Discord API {response.status_code}:{Style.RESET_ALL} retrying in "
                f"{wait_seconds:.1f}s {Fore.LIGHTBLACK_EX}(attempt {attempt}/{MAX_API_RETRIES}){Style.RESET_ALL}"
            )
            time.sleep(wait_seconds)
            continue

        return response

    return last_response


def run_sync():
    """Runs the emoji sync sequence native to emoji.py. Safe to be executed at startup."""
    if not TOKEN:
        logger.warning(f"{Fore.YELLOW}Skipping EmojiSync:{Style.RESET_ALL} No token found in .env files.")
        return

    emoji_py_path = os.path.join(BASE_DIR, "skylinebot", "style", "emoji.py")
    try:
        with open(emoji_py_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as err:
        logger.error(f"{Fore.RED}EmojiSync failed:{Style.RESET_ALL} Could not read emoji.py {Fore.LIGHTBLACK_EX}({err}){Style.RESET_ALL}")
        return

    matches = set(re.findall(r"<(a?):(\w+):(\d+)>", content))
    if not matches:
        logger.info(f"{Fore.CYAN}EmojiSync:{Style.RESET_ALL} No custom emojis found in emoji.py to sync.")
        return

    logger.system(f"{Fore.MAGENTA}Starting Native Application Emoji Sync...{Style.RESET_ALL}")

    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json",
    }

    app_id = str(APP_ID or "").strip()
    if not app_id:
        try:
            r = _discord_api_request(
                "GET",
                "https://discord.com/api/v10/users/@me",
                headers=headers,
            )
        except RequestException as err:
            logger.error(
                f"{Fore.RED}EmojiSync API Error:{Style.RESET_ALL} Could not fetch bot info "
                f"{Fore.LIGHTBLACK_EX}({err}){Style.RESET_ALL}"
            )
            return

        if r is None or r.status_code != 200:
            status_code = r.status_code if r is not None else "N/A"
            retry_after = _safe_retry_after_seconds(r)
            retry_hint = f" retry-after={retry_after:.1f}s" if retry_after > 0 else ""
            logger.error(
                f"{Fore.RED}EmojiSync API Error:{Style.RESET_ALL} Failed to fetch bot info "
                f"{Fore.LIGHTBLACK_EX}[HTTP {status_code}{retry_hint}]{Style.RESET_ALL}"
            )
            return

        bot_info = r.json()
        app_id = bot_info.get("id")

    try:
        r = _discord_api_request(
            "GET",
            f"https://discord.com/api/v10/applications/{app_id}/emojis",
            headers=headers,
        )
    except RequestException as err:
        logger.error(
            f"{Fore.RED}EmojiSync API Error:{Style.RESET_ALL} Failed to fetch application emojis "
            f"{Fore.LIGHTBLACK_EX}({err}){Style.RESET_ALL}"
        )
        return

    if r is None or r.status_code != 200:
        status_code = r.status_code if r is not None else "N/A"
        retry_after = _safe_retry_after_seconds(r)
        retry_hint = f" retry-after={retry_after:.1f}s" if retry_after > 0 else ""
        scope = _rate_limit_scope(r)
        if status_code == 429:
            scope_hint = f" scope={scope}" if scope else ""
            logger.warning(
                f"{Fore.YELLOW}EmojiSync skipped this run due to rate limit:{Style.RESET_ALL} "
                f"{Fore.LIGHTBLACK_EX}[HTTP 429{retry_hint}{scope_hint}]{Style.RESET_ALL}"
            )
        else:
            logger.error(
                f"{Fore.RED}EmojiSync API Error:{Style.RESET_ALL} Failed to fetch application emojis "
                f"{Fore.LIGHTBLACK_EX}[HTTP {status_code}{retry_hint}]{Style.RESET_ALL}"
            )
        return

    data = r.json()
    app_emojis = data.get("items", []) if isinstance(data, dict) else data

    logger.info(
        f"{Fore.CYAN}Config Search:{Style.RESET_ALL} Found {Fore.YELLOW}{len(matches)}{Style.RESET_ALL} "
        f"unique templates {Fore.LIGHTBLACK_EX}|{Style.RESET_ALL} Application hosts "
        f"{Fore.GREEN}{len(app_emojis)}{Style.RESET_ALL} App Emojis"
    )

    updated = False
    skipped = 0
    uploaded = 0
    fixed = 0
    failed = 0

    for animated_str, name, old_id in matches:
        animated = animated_str == "a"

        existing = next((e for e in app_emojis if e["id"] == old_id), None) or next(
            (e for e in app_emojis if e["name"] == name), None
        )

        if existing:
            new_id = existing["id"]
            if old_id != new_id:
                old_str = f"<{animated_str}:{name}:{old_id}>"
                new_str = f"<{animated_str}:{existing['name']}:{new_id}>"
                content = content.replace(old_str, new_str)
                updated = True
                fixed += 1
                logger.warning(f"{Fore.YELLOW}Auto-fixing ID:{Style.RESET_ALL} {name} {Fore.LIGHTBLACK_EX}->{Style.RESET_ALL} {new_id}")
            else:
                skipped += 1
            continue

        logger.info(f"{Fore.BLUE}Uploading:{Style.RESET_ALL} {name} {Fore.LIGHTBLACK_EX}(not found on Discord){Style.RESET_ALL}")

        image_data = fetch_emoji_image(old_id, animated)
        if not image_data:
            logger.error(f"{Fore.RED}Error loading emoji image:{Style.RESET_ALL} {name} {Fore.LIGHTBLACK_EX}[ID: {old_id}]{Style.RESET_ALL}")
            failed += 1
            continue

        mime_type = "image/gif" if animated else "image/webp"
        base64_data = base64.b64encode(image_data).decode("utf-8")
        image_uri = f"data:{mime_type};base64,{base64_data}"

        post_data = {"name": name, "image": image_uri}
        try:
            r2 = _discord_api_request(
                "POST",
                f"https://discord.com/api/v10/applications/{app_id}/emojis",
                headers=headers,
                json=post_data,
            )
        except RequestException as err:
            logger.error(
                f"{Fore.RED}Discord rejected:{Style.RESET_ALL} {name} "
                f"{Fore.LIGHTBLACK_EX}->{Style.RESET_ALL} network error: {err}"
            )
            failed += 1
            continue

        if r2 is not None and r2.status_code in (200, 201):
            new_emoji = r2.json()
            new_id = new_emoji["id"]

            old_str = f"<{animated_str}:{name}:{old_id}>"
            new_str = f"<{animated_str}:{new_emoji['name']}:{new_id}>"
            content = content.replace(old_str, new_str)

            app_emojis.append(new_emoji)

            updated = True
            uploaded += 1
            logger.success(
                f"{Fore.GREEN}Target uploaded:{Style.RESET_ALL} {name} "
                f"{Fore.LIGHTBLACK_EX}[Saved as ID: {new_id}]{Style.RESET_ALL}"
            )
        else:
            status_code = r2.status_code if r2 is not None else "N/A"
            retry_after = _safe_retry_after_seconds(r2)
            retry_hint = f" retry-after={retry_after:.1f}s" if retry_after > 0 else ""
            text = r2.text if r2 is not None else "no response"
            logger.error(
                f"{Fore.RED}Discord rejected:{Style.RESET_ALL} {name} "
                f"{Fore.LIGHTBLACK_EX}->{Style.RESET_ALL} [HTTP {status_code}{retry_hint}] {text}"
            )
            failed += 1

    if updated:
        try:
            with open(emoji_py_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.success(
                f"{Fore.MAGENTA}EmojiSync snapshot saved:{Style.RESET_ALL} "
                f"Dynamically overwrote {Fore.YELLOW}emoji.py{Style.RESET_ALL} to reflect API state."
            )
        except Exception as err:
            logger.error(
                f"{Fore.RED}Sync write blocked:{Style.RESET_ALL} Could not patch emoji.py "
                f"{Fore.LIGHTBLACK_EX}({err}){Style.RESET_ALL}"
            )

    summary_parts = []
    if skipped:
        summary_parts.append(f"{Fore.GREEN}{skipped} perfectly matching{Style.RESET_ALL}")
    if fixed:
        summary_parts.append(f"{Fore.YELLOW}{fixed} ID mismatches fixed{Style.RESET_ALL}")
    if uploaded:
        summary_parts.append(f"{Fore.CYAN}{uploaded} newly uploaded{Style.RESET_ALL}")
    if failed:
        summary_parts.append(f"{Fore.RED}{failed} download/upload failures{Style.RESET_ALL}")

    if summary_parts:
        logger.system(f"{Fore.MAGENTA}EmojiSync completed:{Style.RESET_ALL} {Fore.LIGHTBLACK_EX}|{Style.RESET_ALL} ".join(summary_parts))


if __name__ == "__main__":
    run_sync()
