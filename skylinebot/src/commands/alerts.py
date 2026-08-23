import asyncio
import datetime
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import discord
import requests
from discord.ext import commands

from skylinebot.bridge.storage import get_collection, mongo_is_transient_cluster_error
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot


def _normalize_alert_entry(entry: dict[str, Any], default_channel: str | None = None) -> dict[str, str] | None:
    source_url = str(entry.get("source_url") or "").strip()
    description = str(entry.get("description") or "").strip()[:400]
    button_text = str(entry.get("button_text") or "ดูรายละเอียด").strip()[:45]
    channel_id = str(entry.get("channel_id") or default_channel or "").strip()
    if not source_url:
        return None
    if channel_id and not channel_id.isdigit():
        channel_id = ""
    return {
        "source_url": source_url[:300],
        "description": description,
        "button_text": button_text,
        "channel_id": channel_id,
    }


def _normalize_alert_entries(raw_entries: Any, *, default_channel: str | None = None, max_items: int = 60) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(raw_entries, (list, tuple)):
        iterable = raw_entries
    elif isinstance(raw_entries, str):
        iterable = [{"source_url": part.strip()} for part in re.split(r"[\n,]+", raw_entries) if part.strip()]
    else:
        iterable = []
    for item in iterable:
        if isinstance(item, str):
            item = {"source_url": item}
        if not isinstance(item, dict):
            continue
        normalized = _normalize_alert_entry(item, default_channel=default_channel)
        if not normalized:
            continue
        duplicate = any(
            prev["source_url"].lower() == normalized["source_url"].lower()
            and prev["channel_id"] == normalized["channel_id"]
            for prev in out
        )
        if duplicate:
            continue
        out.append(normalized)
        if len(out) >= max_items:
            break
    return out


def _default_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "notify_channel_id": None,
        "mention_role_ids": [],
        "cooldown_seconds": 60,
        "platforms": {
            "twitch": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "tiktok": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "github": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "youtube": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
            "facebook": {"enabled": False, "entries": [], "message_template": "{platform}: {title} {url}"},
        },
    }


def _normalize_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = _default_settings()
    src = payload or {}
    merged["enabled"] = bool(src.get("enabled"))
    channel_id = str(src.get("notify_channel_id") or "").strip()
    merged["notify_channel_id"] = channel_id if channel_id.isdigit() else None
    try:
        cooldown = int(src.get("cooldown_seconds") or 60)
    except (TypeError, ValueError):
        cooldown = 60
    merged["cooldown_seconds"] = max(10, min(3600, cooldown))

    role_ids: list[str] = []
    for role_id in src.get("mention_role_ids") or []:
        role_text = str(role_id or "").strip()
        if role_text.isdigit() and role_text not in role_ids:
            role_ids.append(role_text)
    merged["mention_role_ids"] = role_ids

    platforms = src.get("platforms") if isinstance(src.get("platforms"), dict) else {}
    for name in ("twitch", "tiktok", "github", "youtube", "facebook"):
        current = platforms.get(name) if isinstance(platforms, dict) else None
        current = current if isinstance(current, dict) else {}
        merged["platforms"][name]["enabled"] = bool(current.get("enabled"))
        raw_entries = current.get("entries")
        if raw_entries is None:
            raw_entries = current.get("sources", [])
        merged["platforms"][name]["entries"] = _normalize_alert_entries(
            raw_entries, default_channel=merged["notify_channel_id"]
        )
        merged["platforms"][name]["message_template"] = str(
            current.get("message_template") or "{platform}: {title} {url}"
        )[:300]

    return merged


class Alerts(commands.Cog):
    PLATFORM_LABELS = {
        "twitch": "Twitch",
        "tiktok": "TikTok",
        "github": "GitHub",
        "youtube": "YouTube",
        "facebook": "Facebook",
    }
    PLATFORM_ALIASES = {
        "twitch": "twitch",
        "tw": "twitch",
        "tiktok": "tiktok",
        "tt": "tiktok",
        "tictok": "tiktok",
        "github": "github",
        "githup": "github",
        "gh": "github",
        "youtube": "youtube",
        "youtu": "youtube",
        "yt": "youtube",
        "facebook": "facebook",
        "fackbook": "facebook",
        "fb": "facebook",
    }
    ITEM_TYPE_LABELS = {
        "live": "ไลฟ์สด",
        "post": "โพสต์ใหม่",
        "event": "อัปเดตใหม่",
    }

    def __init__(self, bot: AutoShardedBot):
        self.bot = bot
        self._worker_task: asyncio.Task | None = None
        self._seen_cache: dict[str, str] = {}
        self._twitch_token: str | None = None
        self._twitch_token_expire_at: datetime.datetime | None = None
        self._transient_db_log_last_at = 0.0

    def _log_worker_error(self, error: Exception) -> None:
        if mongo_is_transient_cluster_error(error):
            now = time.monotonic()
            if (now - float(self._transient_db_log_last_at or 0.0)) >= 45.0:
                self._transient_db_log_last_at = now
                logger.warning(f"Alerts worker transient DB issue (will retry): {error}")
            return
        logger.error(f"Alerts worker error: {error}")

    @staticmethod
    def _extract_tiktok_username_from_url(source_url: str) -> str | None:
        text = str(source_url or "").strip()
        if not text:
            return None
        match = re.search(r"tiktok\.com/@([A-Za-z0-9._]+)", text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_json_script(html: str, script_id: str) -> dict[str, Any]:
        pattern = rf'<script[^>]*id="{re.escape(script_id)}"[^>]*>(.*?)</script>'
        match = re.search(pattern, html or "", re.DOTALL | re.IGNORECASE)
        if not match:
            return {}
        raw = (match.group(1) or "").strip()
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
            return decoded if isinstance(decoded, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _pick_latest_tiktok_item(item_modules: list[dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
        best: tuple[str, dict[str, Any]] | None = None
        best_time = -1
        for module in item_modules:
            if not isinstance(module, dict):
                continue
            for item_id, payload in module.items():
                if not isinstance(payload, dict):
                    continue
                clean_id = str(payload.get("id") or item_id or "").strip()
                if not clean_id:
                    continue
                created_raw = payload.get("createTime")
                try:
                    created_at = int(created_raw) if created_raw is not None else 0
                except (TypeError, ValueError):
                    created_at = 0
                if created_at <= 0:
                    try:
                        created_at = int(clean_id)
                    except (TypeError, ValueError):
                        created_at = 0
                if created_at > best_time:
                    best_time = created_at
                    best = (clean_id, payload)
        return best

    @staticmethod
    def _extract_room_id_from_payload(payload: dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return ""
        candidates: list[Any] = [
            (((payload.get("LiveRoom") or {}).get("liveRoomUserInfo") or {}).get("user") or {}).get("roomId"),
            (((payload.get("LiveRoom") or {}).get("userInfo") or {}).get("user") or {}).get("roomId"),
        ]
        user_module = payload.get("UserModule")
        if isinstance(user_module, dict):
            users_map = user_module.get("users")
            if isinstance(users_map, dict):
                for row in users_map.values():
                    if not isinstance(row, dict):
                        continue
                    candidates.append(row.get("roomId"))
                    candidates.append(row.get("liveRoomId"))
        for value in candidates:
            text = str(value or "").strip()
            if text.isdigit():
                return text
        return ""

    async def cog_load(self):
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._alerts_worker_loop())

    def cog_unload(self):
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()

    async def _wait_until_ready_safely(self) -> bool:
        while not self.bot.is_closed():
            # This worker can be created before bot.login(); avoid
            # wait_until_ready() RuntimeError by polling readiness directly.
            if getattr(self.bot, "user", None) is not None and self.bot.is_ready():
                return True
            await asyncio.sleep(1)
        return False

    async def _get_settings(self, guild_id: int) -> dict[str, Any]:
        try:
            col = await get_collection("guilds")
            doc = await col.find_one({"guild_id": guild_id}, {"alerts_settings_fallback": 1, "_id": 0})
            return _normalize_settings((doc or {}).get("alerts_settings_fallback"))
        except Exception:
            return _default_settings()

    async def _save_settings(self, guild_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_settings(payload)
        try:
            col = await get_collection("guilds")
            await col.update_one(
                {"guild_id": guild_id},
                {"$set": {"alerts_settings_fallback": normalized}},
                upsert=True,
            )
        except Exception:
            pass
        return normalized

    def _resolve_platform(self, raw_platform: str) -> str | None:
        key = str(raw_platform or "").strip().lower()
        return self.PLATFORM_ALIASES.get(key)

    async def _require_manage_guild(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            await ctx.reply("คำสั่งนี้ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น")
            return False
        if not getattr(ctx.author.guild_permissions, "manage_guild", False):
            await ctx.reply("ต้องมีสิทธิ์ `Manage Server` เพื่อใช้คำสั่งนี้")
            return False
        return True

    def _build_alert_key(
        self,
        guild_id: int,
        platform: str,
        source_url: str,
        channel_id: str,
        item_type: str = "event",
    ) -> str:
        return f"{guild_id}:{platform}:{source_url.strip().lower()}:{channel_id.strip()}:{item_type.strip().lower()}"

    async def _alerts_worker_loop(self):
        if not await self._wait_until_ready_safely():
            return
        while not self.bot.is_closed():
            try:
                await self._poll_all_alerts()
            except Exception as error:
                self._log_worker_error(error)
            await asyncio.sleep(20)

    async def _poll_all_alerts(self):
        col = await get_collection("guilds")
        docs = col.find({"alerts_settings_fallback.enabled": True}, {"guild_id": 1, "alerts_settings_fallback": 1})
        async for doc in docs:
            guild_id = int(doc.get("guild_id") or 0)
            if guild_id <= 0:
                continue
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            settings = _normalize_settings(doc.get("alerts_settings_fallback"))
            await self._poll_guild_alerts(guild, settings)

    async def _poll_guild_alerts(self, guild: discord.Guild, settings: dict[str, Any]):
        cooldown = int(settings.get("cooldown_seconds", 60) or 60)
        if cooldown < 10:
            cooldown = 10
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        mention_roles = [f"<@&{role_id}>" for role_id in settings.get("mention_role_ids", []) if str(role_id).isdigit()]
        mention_text = " ".join(mention_roles).strip()
        default_channel = str(settings.get("notify_channel_id") or "").strip()

        for platform in ("twitch", "tiktok", "github", "youtube", "facebook"):
            platform_conf = settings.get("platforms", {}).get(platform, {})
            if not platform_conf.get("enabled"):
                continue
            template = str(platform_conf.get("message_template") or "{platform}: {title} {url}")
            for entry in platform_conf.get("entries", []):
                source_url = str(entry.get("source_url") or "").strip()
                if not source_url:
                    continue
                target_channel_id = str(entry.get("channel_id") or default_channel or "").strip()
                if not target_channel_id.isdigit():
                    continue
                target_channel = guild.get_channel(int(target_channel_id))
                if not target_channel or not isinstance(target_channel, (discord.TextChannel, discord.Thread)):
                    continue
                items = await self._fetch_alert_items(platform, source_url)
                if not items:
                    continue
                for latest in items:
                    latest_id = str(latest.get("id") or "").strip()
                    item_type = str(latest.get("item_type") or "event").strip().lower() or "event"
                    if not latest_id:
                        continue
                    key = self._build_alert_key(guild.id, platform, source_url, target_channel_id, item_type=item_type)
                    cache_key = f"{key}:id"
                    if self._seen_cache.get(cache_key) == latest_id:
                        continue
                    cooldown_key = f"{key}:ts"
                    last_ts_raw = self._seen_cache.get(cooldown_key)
                    last_ts = int(last_ts_raw) if str(last_ts_raw or "").isdigit() else 0
                    if now_ts - last_ts < cooldown:
                        continue
                    await self._send_alert_message(
                        channel=target_channel,
                        platform=platform,
                        latest=latest,
                        template=template,
                        entry=entry,
                        mention_text=mention_text,
                    )
                    self._seen_cache[cache_key] = latest_id
                    self._seen_cache[cooldown_key] = str(now_ts)


    async def _send_alert_message(
        self,
        *,
        channel: discord.abc.Messageable,
        platform: str,
        latest: dict[str, str],
        template: str,
        entry: dict[str, str],
        mention_text: str,
    ):
        url = str(latest.get("url") or "").strip()
        title = str(latest.get("title") or "New update")
        item_type = str(latest.get("item_type") or "event").strip().lower() or "event"
        type_label = self.ITEM_TYPE_LABELS.get(item_type, "Update")
        platform_label = self.PLATFORM_LABELS.get(platform, platform.title())
        content = template.replace("{platform}", platform_label).replace("{title}", title).replace("{url}", url)
        if mention_text:
            content = f"{mention_text}\n{content}"
        embed = discord.Embed(
            title=f"{platform_label} | {type_label}",
            description=str(entry.get("description") or latest.get("summary") or "").strip()[:400] or None,
            color=discord.Color.blurple(),
        )
        if url:
            embed.add_field(name="Link", value=url[:1024], inline=False)
        view = None
        button_text = str(entry.get("button_text") or "Open").strip()[:45] or "Open"
        if url:
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label=button_text, style=discord.ButtonStyle.link, url=url))
        try:
            await channel.send(content=content, embed=embed, view=view)
        except Exception as error:
            logger.error(f"Failed to send alert message: {error}")

    async def _fetch_alert_items(self, platform: str, source_url: str) -> list[dict[str, str]]:
        if platform == "twitch":
            return await self._fetch_twitch_items(source_url)
        if platform == "tiktok":
            return await self._fetch_tiktok_items(source_url)
        if platform == "github":
            item = await self._fetch_github_latest(source_url)
            return [item] if item else []
        if platform == "youtube":
            return await self._fetch_youtube_items(source_url)
        if platform == "facebook":
            return await self._fetch_facebook_items(source_url)
        item = await self._fetch_other_latest(source_url)
        return [item] if item else []

    async def _http_get_json(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, str] | None = None) -> Any:
        def _run():
            merged_headers = {"User-Agent": "SkylineBOT/1.0"}
            if headers:
                merged_headers.update(headers)
            response = requests.get(url, headers=merged_headers, params=params, timeout=18)
            response.raise_for_status()
            return response.json()

        return await asyncio.to_thread(_run)

    async def _http_get_text(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, str] | None = None) -> str:
        def _run():
            merged_headers = {"User-Agent": "SkylineBOT/1.0"}
            if headers:
                merged_headers.update(headers)
            response = requests.get(url, headers=merged_headers, params=params, timeout=18)
            response.raise_for_status()
            return response.text

        return await asyncio.to_thread(_run)

    async def _http_post_json(self, url: str, *, headers: dict[str, str] | None = None, data: dict[str, str] | None = None) -> Any:
        def _run():
            merged_headers = {"User-Agent": "SkylineBOT/1.0"}
            if headers:
                merged_headers.update(headers)
            response = requests.post(url, headers=merged_headers, data=data, timeout=18)
            response.raise_for_status()
            return response.json()

        return await asyncio.to_thread(_run)

    async def _get_twitch_access_token(self) -> str | None:
        now = datetime.datetime.now(datetime.timezone.utc)
        if self._twitch_token and self._twitch_token_expire_at and now < self._twitch_token_expire_at:
            return self._twitch_token

        client_id = os.getenv("TWITCH_CLIENT_ID", "").strip()
        client_secret = os.getenv("TWITCH_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return None

        try:
            data = await self._http_post_json(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                },
            )
            token = str(data.get("access_token") or "").strip()
            expires_in = int(data.get("expires_in") or 0)
            if not token:
                return None
            self._twitch_token = token
            self._twitch_token_expire_at = now + datetime.timedelta(seconds=max(0, expires_in - 60))
            return token
        except Exception:
            return None

    async def _fetch_twitch_latest(self, source_url: str) -> dict[str, str] | None:
        token = await self._get_twitch_access_token()
        client_id = os.getenv("TWITCH_CLIENT_ID", "").strip()
        if not token or not client_id:
            return None
        match = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", source_url)
        if not match:
            return None
        login = match.group(1)
        try:
            payload = await self._http_get_json(
                "https://api.twitch.tv/helix/streams",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Client-Id": client_id,
                },
                params={"user_login": login},
            )
            rows = payload.get("data") or []
            if not rows:
                return None
            stream = rows[0]
            return {
                "id": str(stream.get("id") or ""),
                "title": str(stream.get("title") or f"{login} live"),
                "url": f"https://www.twitch.tv/{login}",
                "summary": str(stream.get("game_name") or ""),
            }
        except Exception:
            return None

    async def _fetch_tiktok_latest(self, source_url: str) -> dict[str, str] | None:
        match = re.search(r"tiktok\.com/@([A-Za-z0-9._]+)", source_url)
        if not match:
            return None
        username = match.group(1)
        profile_url = f"https://www.tiktok.com/@{username}"
        try:
            html = await self._http_get_text(
                profile_url,
                headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.tiktok.com/",
                },
            )
        except Exception:
            return None

        try:
            section = re.search(
                r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
                html,
                re.DOTALL,
            )
            payload = json.loads(section.group(1)) if section else {}
            item_module = (
                payload.get("__DEFAULT_SCOPE__")
                or {}
            ).get("webapp.user-detail", {}).get("itemModule", {})
            if not isinstance(item_module, dict) or not item_module:
                item_module = (
                    ((payload.get("__DEFAULT_SCOPE__") or {}).get("webapp.user-detail") or {}).get("itemList") or {}
                )
            if isinstance(item_module, dict) and item_module:
                first_id = sorted(item_module.keys(), reverse=True)[0]
                item = item_module.get(first_id) or {}
                video_id = str(item.get("id") or first_id)
                desc = str(item.get("desc") or "").strip()
                title = desc.split("\n")[0][:160] if desc else f"โพสต์ใหม่จาก @{username}"
                return {
                    "id": video_id,
                    "title": title,
                    "url": f"https://www.tiktok.com/@{username}/video/{video_id}",
                    "summary": "",
                }
        except Exception:
            pass

        fallback = re.search(r'"itemId":"(\d{8,})"', html)
        if fallback:
            video_id = fallback.group(1)
            return {
                "id": video_id,
                "title": f"โพสต์ใหม่จาก @{username}",
                "url": f"https://www.tiktok.com/@{username}/video/{video_id}",
                "summary": "",
            }
        return None

    async def _fetch_github_latest(self, source_url: str) -> dict[str, str] | None:
        match = re.search(r"github\.com/([^/]+)/([^/?#]+)", source_url)
        if not match:
            return None
        owner = match.group(1)
        repo = match.group(2).replace(".git", "")
        token = os.getenv("GITHUB_TOKEN", "").strip()
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            rows = await self._http_get_json(
                f"https://api.github.com/repos/{owner}/{repo}/events",
                headers=headers,
                params={"per_page": "1"},
            )
            if not isinstance(rows, list) or not rows:
                return None
            row = rows[0]
            repo_name = str((row.get("repo") or {}).get("name") or f"{owner}/{repo}")
            event_type = str(row.get("type") or "Event")
            actor = str((row.get("actor") or {}).get("login") or "")
            event_id = str(row.get("id") or "")
            title = f"{repo_name}: {event_type}" + (f" โดย {actor}" if actor else "")
            url = f"https://github.com/{owner}/{repo}"
            return {"id": event_id, "title": title, "url": url, "summary": ""}
        except Exception:
            return None

    async def _resolve_youtube_channel_id(self, source_url: str) -> str | None:
        direct = re.search(r"youtube\.com/channel/([A-Za-z0-9_-]+)", source_url)
        if direct:
            return direct.group(1)
        try:
            html = await self._http_get_text(source_url)
            match = re.search(r'"channelId":"(UC[A-Za-z0-9_-]{20,})"', html)
            if match:
                return match.group(1)
        except Exception:
            return None
        return None

    async def _fetch_youtube_latest(self, source_url: str) -> dict[str, str] | None:
        channel_id = await self._resolve_youtube_channel_id(source_url)
        if not channel_id:
            return None
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            text = await self._http_get_text(feed_url)
            root = ET.fromstring(text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entry = root.find("atom:entry", ns)
            if entry is None:
                return None
            video_id = entry.findtext("atom:id", default="", namespaces=ns)
            title = entry.findtext("atom:title", default="New video", namespaces=ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            return {
                "id": str(video_id),
                "title": str(title),
                "url": str(link),
                "summary": "",
            }
        except Exception:
            return None

    async def _fetch_facebook_latest(self, source_url: str) -> dict[str, str] | None:
        token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
        if not token:
            return None
        cleaned = source_url.rstrip("/")
        page = cleaned.rsplit("/", 1)[-1].strip()
        page = page.replace("https://www.facebook.com/", "").replace("https://facebook.com/", "")
        page = page.strip("/")
        if not page:
            return None
        try:
            payload = await self._http_get_json(
                f"https://graph.facebook.com/v19.0/{page}/posts",
                params={
                    "fields": "id,message,permalink_url,created_time",
                    "limit": "1",
                    "access_token": token,
                },
            )
            rows = payload.get("data") or []
            if not rows:
                return None
            row = rows[0]
            return {
                "id": str(row.get("id") or ""),
                "title": str((row.get("message") or "Facebook update")).split("\n")[0][:160],
                "url": str(row.get("permalink_url") or source_url),
                "summary": "",
            }
        except Exception:
            return None

    async def _fetch_other_latest(self, source_url: str) -> dict[str, str] | None:
        try:
            text = await self._http_get_text(source_url)
        except Exception:
            return None
        try:
            root = ET.fromstring(text)
        except Exception:
            return None

        # RSS
        item = root.find("./channel/item")
        if item is not None:
            guid = item.findtext("guid", default="") or item.findtext("link", default="")
            title = item.findtext("title", default="New update")
            url = item.findtext("link", default=source_url)
            return {"id": str(guid), "title": str(title), "url": str(url), "summary": ""}

        # Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)
        if entry is not None:
            entry_id = entry.findtext("atom:id", default="", namespaces=ns)
            title = entry.findtext("atom:title", default="New update", namespaces=ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.attrib.get("href", source_url) if link_el is not None else source_url
            return {"id": str(entry_id), "title": str(title), "url": str(link), "summary": ""}
        return None

    async def _http_get_text_with_final_url(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        def _run():
            merged_headers = {"User-Agent": "SkylineBOT/1.0"}
            if headers:
                merged_headers.update(headers)
            response = requests.get(url, headers=merged_headers, params=params, timeout=18, allow_redirects=True)
            response.raise_for_status()
            return response.text, str(response.url)

        return await asyncio.to_thread(_run)

    async def _fetch_twitch_items(self, source_url: str) -> list[dict[str, str]]:
        token = await self._get_twitch_access_token()
        client_id = os.getenv("TWITCH_CLIENT_ID", "").strip()
        if not token or not client_id:
            return []
        match = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", source_url)
        if not match:
            return []

        login = match.group(1)
        headers = {"Authorization": f"Bearer {token}", "Client-Id": client_id}
        items: list[dict[str, str]] = []
        try:
            user_payload = await self._http_get_json(
                "https://api.twitch.tv/helix/users",
                headers=headers,
                params={"login": login},
            )
            user_rows = user_payload.get("data") or []
            if not user_rows:
                return []
            user = user_rows[0]
            user_id = str(user.get("id") or "").strip()
            display_name = str(user.get("display_name") or login)

            stream_payload = await self._http_get_json(
                "https://api.twitch.tv/helix/streams",
                headers=headers,
                params={"user_id": user_id},
            )
            stream_rows = stream_payload.get("data") or []
            if stream_rows:
                stream = stream_rows[0]
                stream_id = str(stream.get("id") or "").strip()
                if stream_id:
                    items.append(
                        {
                            "id": f"live:{stream_id}",
                            "item_type": "live",
                            "title": str(stream.get("title") or f"{display_name} live"),
                            "url": f"https://www.twitch.tv/{login}",
                            "summary": str(stream.get("game_name") or ""),
                        }
                    )

            video_payload = await self._http_get_json(
                "https://api.twitch.tv/helix/videos",
                headers=headers,
                params={"user_id": user_id, "type": "archive", "first": "1"},
            )
            video_rows = video_payload.get("data") or []
            if video_rows:
                video = video_rows[0]
                video_id = str(video.get("id") or "").strip()
                video_url = str(video.get("url") or f"https://www.twitch.tv/{login}/videos")
                if video_id:
                    items.append(
                        {
                            "id": f"post:{video_id}",
                            "item_type": "post",
                            "title": str(video.get("title") or f"คลิปใหม่จาก {display_name}"),
                            "url": video_url,
                            "summary": str(video.get("description") or "")[:300],
                        }
                    )
        except Exception:
            return []
        return items

    async def _fetch_tiktok_items(self, source_url: str) -> list[dict[str, str]]:
        username = self._extract_tiktok_username_from_url(source_url)
        if not username:
            try:
                _, final_url = await self._http_get_text_with_final_url(source_url)
                username = self._extract_tiktok_username_from_url(final_url)
            except Exception:
                username = None
        if not username:
            return []

        profile_url = f"https://www.tiktok.com/@{username}"
        browser_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tiktok.com/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        try:
            html = await self._http_get_text(profile_url, headers=browser_headers)
        except Exception:
            return []

        items: list[dict[str, str]] = []
        sigi_payload = self._extract_json_script(html, "SIGI_STATE")
        universal_payload = self._extract_json_script(html, "__UNIVERSAL_DATA_FOR_REHYDRATION__")

        room_id = ""
        if sigi_payload:
            room_id = self._extract_room_id_from_payload(sigi_payload)
        if not room_id and universal_payload:
            room_id = self._extract_room_id_from_payload(universal_payload)
        if not room_id:
            live_match = (
                re.search(r'"liveRoomId":"(\d+)"', html)
                or re.search(r'"roomId":"(\d+)"', html)
                or re.search(r'"room_id":"(\d+)"', html)
            )
            if live_match:
                room_id = live_match.group(1)
        if room_id:
            items.append(
                {
                    "id": f"live:{room_id}",
                    "item_type": "live",
                    "title": f"@{username} กำลังไลฟ์สด",
                    "url": f"https://www.tiktok.com/@{username}/live",
                    "summary": "",
                }
            )

        item_modules: list[dict[str, Any]] = []
        if universal_payload:
            user_detail = (universal_payload.get("__DEFAULT_SCOPE__") or {}).get("webapp.user-detail") or {}
            maybe_module = user_detail.get("itemModule")
            if isinstance(maybe_module, dict) and maybe_module:
                item_modules.append(maybe_module)
            maybe_list = user_detail.get("itemList")
            if isinstance(maybe_list, dict) and maybe_list:
                item_modules.append(maybe_list)
        if sigi_payload:
            sigi_module = sigi_payload.get("ItemModule")
            if isinstance(sigi_module, dict) and sigi_module:
                item_modules.append(sigi_module)

        picked = self._pick_latest_tiktok_item(item_modules)
        if picked:
            video_id, post_payload = picked
            desc = str(post_payload.get("desc") or "").strip()
            author = str(post_payload.get("author") or username).strip() or username
            title = desc.split("\n")[0][:160] if desc else f"โพสต์ใหม่จาก @{author}"
            items.append(
                {
                    "id": f"post:{video_id}",
                    "item_type": "post",
                    "title": title,
                    "url": f"https://www.tiktok.com/@{author}/video/{video_id}",
                    "summary": "",
                }
            )
            return items

        fallback = re.search(r'"itemId":"(\d{8,})"', html) or re.search(r"/video/(\d{8,})", html)
        if fallback:
            video_id = fallback.group(1)
            items.append(
                {
                    "id": f"post:{video_id}",
                    "item_type": "post",
                    "title": f"โพสต์ใหม่จาก @{username}",
                    "url": f"https://www.tiktok.com/@{username}/video/{video_id}",
                    "summary": "",
                }
            )
        return items

    async def _fetch_youtube_items(self, source_url: str) -> list[dict[str, str]]:
        channel_id = await self._resolve_youtube_channel_id(source_url)
        if not channel_id:
            return []

        items: list[dict[str, str]] = []
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            text = await self._http_get_text(feed_url)
            root = ET.fromstring(text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entry = root.find("atom:entry", ns)
            if entry is not None:
                video_id = str(entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
                title = str(entry.findtext("atom:title", default="วิดีโอใหม่", namespaces=ns) or "วิดีโอใหม่")
                link_el = entry.find("atom:link", ns)
                link = str(link_el.attrib.get("href", "")) if link_el is not None else ""
                if video_id:
                    items.append(
                        {
                            "id": f"post:{video_id}",
                            "item_type": "post",
                            "title": title,
                            "url": link,
                            "summary": "",
                        }
                    )
        except Exception:
            pass

        try:
            _, final_url = await self._http_get_text_with_final_url(f"https://www.youtube.com/channel/{channel_id}/live")
            watch_match = re.search(r"(https?://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11})", final_url)
            if watch_match:
                live_url = watch_match.group(1)
                live_id_match = re.search(r"v=([A-Za-z0-9_-]{11})", live_url)
                live_id = live_id_match.group(1) if live_id_match else live_url
                items.append(
                    {
                        "id": f"live:{live_id}",
                        "item_type": "live",
                        "title": "ไลฟ์สดบน YouTube",
                        "url": live_url,
                        "summary": "",
                    }
                )
        except Exception:
            pass

        return items

    async def _fetch_facebook_items(self, source_url: str) -> list[dict[str, str]]:
        token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
        if not token:
            return []

        cleaned = source_url.rstrip("/")
        page = cleaned.rsplit("/", 1)[-1].strip()
        page = page.replace("https://www.facebook.com/", "").replace("https://facebook.com/", "")
        page = page.strip("/")
        if not page:
            return []

        items: list[dict[str, str]] = []
        try:
            payload = await self._http_get_json(
                f"https://graph.facebook.com/v19.0/{page}/posts",
                params={
                    "fields": "id,message,permalink_url,created_time",
                    "limit": "1",
                    "access_token": token,
                },
            )
            rows = payload.get("data") or []
            if rows:
                row = rows[0]
                post_id = str(row.get("id") or "").strip()
                if post_id:
                    items.append(
                        {
                            "id": f"post:{post_id}",
                            "item_type": "post",
                            "title": str((row.get("message") or "Facebook update")).split("\n")[0][:160],
                            "url": str(row.get("permalink_url") or source_url),
                            "summary": "",
                        }
                    )
        except Exception:
            pass

        try:
            live_payload = await self._http_get_json(
                f"https://graph.facebook.com/v19.0/{page}/live_videos",
                params={
                    "fields": "id,title,description,permalink_url,status",
                    "limit": "5",
                    "access_token": token,
                },
            )
            live_rows = live_payload.get("data") or []
            for row in live_rows:
                status = str(row.get("status") or "").upper()
                if status and status not in {"LIVE", "LIVE_NOW", "ONGOING", "ACTIVE"}:
                    continue
                live_id = str(row.get("id") or "").strip()
                if not live_id:
                    continue
                items.append(
                    {
                        "id": f"live:{live_id}",
                        "item_type": "live",
                        "title": str(row.get("title") or "Facebook ไลฟ์สด"),
                        "url": str(row.get("permalink_url") or source_url),
                        "summary": str(row.get("description") or "")[:300],
                    }
                )
                break
        except Exception:
            pass

        return items

    @commands.hybrid_group(
        name="alerts",
        with_app_command=True,
        invoke_without_command=True,
        help="จัดการการแจ้งเตือนโซเชียลและแพลตฟอร์มต่าง ๆ",
    )
    async def alerts(self, ctx: commands.Context):
        if not await self._require_manage_guild(ctx):
            return
        await ctx.reply("Available commands: `alerts status`, `alerts enable`, `alerts channel`, `alerts toggle`, `alerts add`, `alerts remove`, `alerts list`")

    @alerts.command(name="status", help="ดูสถานะระบบแจ้งเตือน")
    async def alerts_status(self, ctx: commands.Context):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        channel_id = settings.get("notify_channel_id")
        channel_text = f"<#{channel_id}>" if channel_id else "ยังไม่ได้ตั้งค่า"
        lines = [
            f"สถานะรวม: {'เปิด' if settings.get('enabled') else 'ปิด'}",
            f"ช่องแจ้งเตือนหลัก: {channel_text}",
            f"คูลดาวน์: {settings.get('cooldown_seconds', 60)} วินาที",
        ]
        for platform in ("twitch", "tiktok", "github", "youtube", "facebook"):
            row = settings.get("platforms", {}).get(platform, {})
            lines.append(
                f"- {self.PLATFORM_LABELS[platform]}: {'เปิด' if row.get('enabled') else 'ปิด'} | รายการ {len(row.get('entries') or [])}"
            )
        await ctx.reply("\n".join(lines))


    @alerts.command(name="enable", help="เปิดหรือปิดระบบแจ้งเตือนอัตโนมัติของกิลด์นี้")
    async def alerts_enable(self, ctx: commands.Context, state: str):
        if not await self._require_manage_guild(ctx):
            return
        state_raw = str(state or "").strip().lower()
        if state_raw not in {"on", "off", "enable", "disable", "true", "false", "1", "0"}:
            await ctx.reply("State must be on/off")
            return
        enabled = state_raw in {"on", "enable", "true", "1"}
        settings = await self._get_settings(ctx.guild.id)
        settings["enabled"] = enabled
        await self._save_settings(ctx.guild.id, settings)
        await ctx.reply(f"Social Alerts: {'enabled' if enabled else 'disabled'}")

    @alerts.command(name="channel", help="ตั้งค่าช่องแจ้งเตือนหลัก")
    async def alerts_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        if not await self._require_manage_guild(ctx):
            return
        settings = await self._get_settings(ctx.guild.id)
        settings["notify_channel_id"] = str(channel.id) if channel else None
        if channel:
            settings["enabled"] = True
        await self._save_settings(ctx.guild.id, settings)
        if channel:
            await ctx.reply(f"ตั้งค่าช่องแจ้งเตือนหลักเป็น {channel.mention} แล้ว")
        else:
            await ctx.reply("ล้างค่าช่องแจ้งเตือนหลักแล้ว")

    @alerts.command(name="toggle", help="เปิด/ปิดแพลตฟอร์มแจ้งเตือน")
    async def alerts_toggle(self, ctx: commands.Context, platform: str, state: str):
        if not await self._require_manage_guild(ctx):
            return
        key = self._resolve_platform(platform)
        if not key:
            await ctx.reply("แพลตฟอร์มไม่ถูกต้อง: twitch, tiktok, github, youtube, facebook")
            return
        state_raw = str(state or "").strip().lower()
        if state_raw not in {"on", "off", "enable", "disable", "true", "false", "1", "0"}:
            await ctx.reply("สถานะต้องเป็น on/off")
            return
        enabled = state_raw in {"on", "enable", "true", "1"}
        settings = await self._get_settings(ctx.guild.id)
        settings["platforms"][key]["enabled"] = enabled
        if enabled:
            settings["enabled"] = True
        await self._save_settings(ctx.guild.id, settings)
        await ctx.reply(f"{self.PLATFORM_LABELS[key]}: {'เปิด' if enabled else 'ปิด'}")

    @alerts.command(name="add", help="เพิ่มรายการแจ้งเตือน (ลิงก์ช่อง/รีโพ/เพจ)")
    async def alerts_add(self, ctx: commands.Context, platform: str, source_url: str, channel: discord.TextChannel | None = None):
        if not await self._require_manage_guild(ctx):
            return
        key = self._resolve_platform(platform)
        if not key:
            await ctx.reply("แพลตฟอร์มไม่ถูกต้อง: twitch, tiktok, github, youtube, facebook")
            return
        entry = _normalize_alert_entry(
            {
                "source_url": source_url,
                "description": "",
                "button_text": "ดูรายละเอียด",
                "channel_id": str(channel.id) if channel else "",
            }
        )
        if not entry:
            await ctx.reply("กรุณาระบุลิงก์ให้ถูกต้อง")
            return
        settings = await self._get_settings(ctx.guild.id)
        entries = settings["platforms"][key].get("entries") or []
        entries = _normalize_alert_entries(entries + [entry], default_channel=settings.get("notify_channel_id"), max_items=60)
        settings["platforms"][key]["entries"] = entries
        settings["platforms"][key]["enabled"] = True
        settings["enabled"] = True
        await self._save_settings(ctx.guild.id, settings)
        await ctx.reply(f"เพิ่มรายการให้ {self.PLATFORM_LABELS[key]} แล้ว: `{entry['source_url']}`")

    @alerts.command(name="remove", help="ลบรายการแจ้งเตือนจากลิงก์")
    async def alerts_remove(self, ctx: commands.Context, platform: str, *, source_url: str):
        if not await self._require_manage_guild(ctx):
            return
        key = self._resolve_platform(platform)
        if not key:
            await ctx.reply("แพลตฟอร์มไม่ถูกต้อง: twitch, tiktok, github, youtube, facebook")
            return
        settings = await self._get_settings(ctx.guild.id)
        entries = settings["platforms"][key].get("entries") or []
        cleaned = [row for row in entries if str(row.get("source_url") or "").strip().lower() != source_url.strip().lower()]
        settings["platforms"][key]["entries"] = cleaned
        await self._save_settings(ctx.guild.id, settings)
        await ctx.reply(f"ลบรายการจาก {self.PLATFORM_LABELS[key]} แล้ว: `{source_url}`")

    @alerts.command(name="list", help="ดูรายการแจ้งเตือนทั้งหมดของแพลตฟอร์ม")
    async def alerts_list(self, ctx: commands.Context, platform: str):
        if not await self._require_manage_guild(ctx):
            return
        key = self._resolve_platform(platform)
        if not key:
            await ctx.reply("แพลตฟอร์มไม่ถูกต้อง: twitch, tiktok, github, youtube, facebook")
            return
        settings = await self._get_settings(ctx.guild.id)
        entries = settings["platforms"][key].get("entries") or []
        if not entries:
            await ctx.reply(f"{self.PLATFORM_LABELS[key]} ยังไม่มีรายการแจ้งเตือน")
            return
        lines = []
        for idx, row in enumerate(entries[:60], start=1):
            channel_text = f" -> <#{row.get('channel_id')}>" if str(row.get("channel_id") or "").isdigit() else ""
            lines.append(f"{idx}. `{row.get('source_url')}`{channel_text}")
        await ctx.reply(f"รายการแจ้งเตือน {self.PLATFORM_LABELS[key]}:\n" + "\n".join(lines))





