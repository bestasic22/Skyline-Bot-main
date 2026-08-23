import datetime,asyncio,discord,os
from discord.ext import commands
from typing import Any

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks
import traceback, sys

from skylinebot.memory.cache import cache

from skylinebot.src.checks.variables import fetch_variables

from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot
import skylinebot.src.modules.dashboard_activity as dashboard_activity

import json
import re
from skylinebot.workflows.notice_cards import build_member_notice_card
import storage.dashboard_config
import storage.invite_members as invite_members_db
import storage.invite_stats as invite_stats_db


def _normalize_plan_tier(raw_plan):
    raw = str(raw_plan or "").strip().lower()
    mapping = {
        "free": "free",
        "silver": "silver",
        "silver_guild_preminum": "silver",
        "silver_guild_premium": "silver",
        "premium_silver": "silver",
        "golden": "golden",
        "gold": "golden",
        "golden_guild_premium": "golden",
        "diamond": "diamond",
        "diamond_guild_premium": "diamond",
        "permanent": "permanent",
        "lifetime": "permanent",
        "forever": "permanent",
        "permanent_guild_premium": "permanent",
        "lifetime_guild_premium": "permanent",
        "ultra": "diamond",
    }
    return mapping.get(raw, "free")


def _plan_at_least(raw_plan, required_tier):
    order = {"free": 0, "silver": 1, "golden": 2, "diamond": 3, "permanent": 4}
    current = order.get(_normalize_plan_tier(raw_plan), 0)
    required = order.get(_normalize_plan_tier(required_tier), 0)
    return current >= required


def _parse_id_list(raw_value):
    if isinstance(raw_value, list):
        return [str(v).strip() for v in raw_value if str(v).strip()]
    if isinstance(raw_value, (tuple, set)):
        return [str(v).strip() for v in raw_value if str(v).strip()]
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except Exception:
            pass
        return [item.strip() for item in text.replace(" ", ",").split(",") if item.strip()]
    return []


def _read_env_discord_id(*names: str) -> str:
    for name in names:
        raw = str(os.getenv(name, "") or "").strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            raw = raw[1:-1].strip()
        if raw.isdigit():
            return raw
    return ""


def _system_trusted_bot_ids() -> set[str]:
    candidates = {
        _read_env_discord_id("DISCORD_CLIENT_ID", "BOT_APPLICATION_ID"),
        _read_env_discord_id("SUPPORT_BOT_APPLICATION_ID", "SUPPORT_BOT_ID"),
    }
    return {item for item in candidates if item}


EXTRA_PROTECTION_CONFIG_KEY_PREFIX = "extra_protection_v1_guild_"


def _coerce_unix_ts_local(value) -> int:
    if isinstance(value, datetime.datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
        return max(0, int(parsed.timestamp()))
    try:
        parsed = int(float(str(value).strip()))
    except Exception:
        return 0
    return max(0, parsed)


def _safe_int_local(value, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except Exception:
        return int(default)


def _default_extra_protection_settings_local() -> dict:
    return {
        "enabled": False,
        "block_bot_add_enabled": True,
        "block_bot_add_armed_at_ts": 0,
        "bot_add_whitelist_user_ids": [],
        "bot_add_whitelist_bot_ids": [],
        "anti_spam_enabled": True,
        "spam_message_limit": 7,
        "spam_window_seconds": 12,
        "anti_mass_mention_enabled": True,
        "mass_mention_limit": 5,
        "delete_discord_invite_enabled": False,
        "delete_scam_links_enabled": True,
        "anti_virus_keywords_enabled": True,
        "custom_virus_keywords": [],
        "detect_nsfw_image_enabled": False,
        "detect_nsfw_image_mode": "allowlist_only",
        "detect_nsfw_image_threshold": 0.72,
        "delete_action": "warn",
        "timeout_seconds": 300,
    }


def _normalize_extra_protection_settings_local(payload: dict | None) -> dict:
    src = payload if isinstance(payload, dict) else {}
    out = _default_extra_protection_settings_local()

    def _to_bool(value, default):
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on", "enabled", "enable"}:
            return True
        if text in {"0", "false", "no", "off", "disabled", "disable"}:
            return False
        return bool(default)

    def _to_int(value, default, minimum, maximum):
        try:
            number = int(str(value).strip())
        except Exception:
            number = int(default)
        return max(minimum, min(maximum, number))

    def _to_float(value, default, minimum, maximum):
        try:
            number = float(str(value).strip())
        except Exception:
            number = float(default)
        if number < minimum:
            return float(minimum)
        if number > maximum:
            return float(maximum)
        return float(number)

    def _to_id_list(raw_value):
        values = []
        if isinstance(raw_value, (list, tuple, set)):
            candidates = [str(item or "").strip() for item in raw_value]
        else:
            text = str(raw_value or "").strip()
            if not text:
                candidates = []
            else:
                try:
                    decoded = json.loads(text)
                except Exception:
                    decoded = None
                if isinstance(decoded, list):
                    candidates = [str(item or "").strip() for item in decoded]
                else:
                    candidates = [item.strip() for item in text.replace("\n", ",").replace(" ", ",").split(",")]
        for item in candidates:
            if item.isdigit() and item not in values:
                values.append(item)
        return values[:120]

    def _to_keywords(raw_value):
        if isinstance(raw_value, (list, tuple, set)):
            candidates = [str(item or "").strip().lower() for item in raw_value]
        else:
            text = str(raw_value or "").strip()
            candidates = [item.strip().lower() for item in re.split(r"[\n\r,]+", text)] if text else []
        values = []
        for item in candidates:
            if not item or item in values:
                continue
            values.append(item[:80])
        return values[:50]

    out["enabled"] = _to_bool(src.get("enabled"), out["enabled"])
    out["block_bot_add_enabled"] = _to_bool(src.get("block_bot_add_enabled"), out["block_bot_add_enabled"])
    out["block_bot_add_armed_at_ts"] = _coerce_unix_ts_local(src.get("block_bot_add_armed_at_ts"))
    out["bot_add_whitelist_user_ids"] = _to_id_list(src.get("bot_add_whitelist_user_ids"))
    out["bot_add_whitelist_bot_ids"] = _to_id_list(src.get("bot_add_whitelist_bot_ids"))
    out["anti_spam_enabled"] = _to_bool(src.get("anti_spam_enabled"), out["anti_spam_enabled"])
    out["spam_message_limit"] = _to_int(src.get("spam_message_limit"), out["spam_message_limit"], 3, 30)
    out["spam_window_seconds"] = _to_int(src.get("spam_window_seconds"), out["spam_window_seconds"], 3, 180)
    out["anti_mass_mention_enabled"] = _to_bool(src.get("anti_mass_mention_enabled"), out["anti_mass_mention_enabled"])
    out["mass_mention_limit"] = _to_int(src.get("mass_mention_limit"), out["mass_mention_limit"], 2, 30)
    out["delete_discord_invite_enabled"] = _to_bool(
        src.get("delete_discord_invite_enabled"),
        out["delete_discord_invite_enabled"],
    )
    out["delete_scam_links_enabled"] = _to_bool(src.get("delete_scam_links_enabled"), out["delete_scam_links_enabled"])
    out["anti_virus_keywords_enabled"] = _to_bool(
        src.get("anti_virus_keywords_enabled"),
        out["anti_virus_keywords_enabled"],
    )
    out["custom_virus_keywords"] = _to_keywords(src.get("custom_virus_keywords"))
    out["detect_nsfw_image_enabled"] = _to_bool(
        src.get("detect_nsfw_image_enabled"),
        out["detect_nsfw_image_enabled"],
    )
    mode = str(src.get("detect_nsfw_image_mode") or out["detect_nsfw_image_mode"]).strip().lower()
    if mode not in {"allowlist_only", "all_except_allowlist"}:
        mode = out["detect_nsfw_image_mode"]
    out["detect_nsfw_image_mode"] = mode
    out["detect_nsfw_image_threshold"] = _to_float(
        src.get("detect_nsfw_image_threshold"),
        out["detect_nsfw_image_threshold"],
        0.05,
        0.995,
    )
    action = str(src.get("delete_action") or out["delete_action"]).strip().lower()
    if action not in {"none", "warn", "mute", "kick", "ban"}:
        action = out["delete_action"]
    out["delete_action"] = action
    out["timeout_seconds"] = _to_int(src.get("timeout_seconds"), out["timeout_seconds"], 30, 86400)
    return out




class on_member_join(commands.Cog):
    _BOT_ADD_STARTUP_GRACE_SECONDS: int = 20

    def __init__(self, bot):
        self.bot: AutoShardedBot = bot
        self._extra_protection_settings_cache: dict[str, dict] = {}
        self._extra_protection_settings_expire: dict[str, float] = {}
        self._extra_protection_cache_ttl_seconds: float = 20.0
        self._system_trusted_bot_ids: set[str] = _system_trusted_bot_ids()
        self._invite_snapshot_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._invite_runtime_context: dict[str, dict[str, Any]] = {}
        self._invite_snapshot_bootstrapped: bool = False
        self._invite_snapshot_task: asyncio.Task | None = None

    def _is_system_trusted_bot(self, bot_id: int | str) -> bool:
        return str(bot_id) in self._system_trusted_bot_ids

    @staticmethod
    def _member_left_guild(member: discord.Member) -> bool:
        guild = getattr(member, "guild", None)
        if guild is None:
            return True
        try:
            return guild.get_member(member.id) is None
        except Exception:
            return False

    @staticmethod
    def _member_joined_at_ts(member: discord.Member) -> int:
        return _coerce_unix_ts_local(getattr(member, "joined_at", None))

    def _bot_start_ts(self) -> int:
        return _coerce_unix_ts_local(getattr(self.bot, "start_time", None))

    def _is_preexisting_member_from_restart(self, member: discord.Member) -> bool:
        joined_ts = self._member_joined_at_ts(member)
        start_ts = self._bot_start_ts()
        if joined_ts <= 0 or start_ts <= 0:
            return False
        return joined_ts < start_ts

    async def _arm_extra_protection_bot_add(self, guild_id: int, settings: dict) -> int:
        now_ts = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
        key = str(guild_id)
        updated = _normalize_extra_protection_settings_local(dict(settings or {}))
        updated["block_bot_add_armed_at_ts"] = now_ts
        self._extra_protection_settings_cache[key] = updated
        self._extra_protection_settings_expire[key] = (
            datetime.datetime.now().timestamp() + self._extra_protection_cache_ttl_seconds
        )
        try:
            config_key = self._extra_protection_config_key(guild_id)
            payload = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
            row = await storage.dashboard_config.get(config_key=config_key)
            if row and row.get("id") is not None:
                await storage.dashboard_config.update(id=row["id"], config_value=payload)
            else:
                await storage.dashboard_config.insert(config_key=config_key, config_value=payload)
        except Exception as error:
            logger.warning(f"Failed to arm extra protection bot-add for guild {guild_id}: {error}")
        return now_ts

    @staticmethod
    def _extra_protection_config_key(guild_id: int) -> str:
        return f"{EXTRA_PROTECTION_CONFIG_KEY_PREFIX}{int(guild_id)}"

    async def _get_extra_protection_settings(self, guild_id: int) -> dict:
        key = str(guild_id)
        now_ts = datetime.datetime.now().timestamp()
        expire_at = float(self._extra_protection_settings_expire.get(key, 0.0) or 0.0)
        cached = self._extra_protection_settings_cache.get(key)
        if cached is not None and now_ts < expire_at:
            return cached
        settings = _default_extra_protection_settings_local()
        try:
            row = await storage.dashboard_config.get(
                config_key=self._extra_protection_config_key(guild_id)
            )
            if row and isinstance(row, dict):
                raw_value = str(row.get("config_value") or "").strip()
                if raw_value:
                    decoded = json.loads(raw_value)
                    if isinstance(decoded, dict):
                        settings = _normalize_extra_protection_settings_local(decoded)
        except Exception:
            settings = _default_extra_protection_settings_local()
        self._extra_protection_settings_cache[key] = settings
        self._extra_protection_settings_expire[key] = now_ts + self._extra_protection_cache_ttl_seconds
        return settings

    @staticmethod
    def _invite_context_key(guild_id: int, user_id: int) -> str:
        return f"{int(guild_id)}:{int(user_id)}"

    async def _fetch_invite_snapshot(self, guild: discord.Guild) -> dict[str, dict[str, Any]]:
        if guild is None:
            return {}
        me = guild.me
        if me is None:
            return {}
        if not bool(getattr(me.guild_permissions, "manage_guild", False)):
            return {}
        try:
            invites = await guild.invites()
        except Exception:
            return {}
        snapshot: dict[str, dict[str, Any]] = {}
        for invite in list(invites or []):
            code = str(getattr(invite, "code", "") or "").strip()
            if not code:
                continue
            inviter = getattr(invite, "inviter", None)
            inviter_id = _safe_int_local(getattr(inviter, "id", 0), 0)
            inviter_name = str(
                getattr(inviter, "display_name", None)
                or getattr(inviter, "name", None)
                or ""
            ).strip()
            invite_url = str(getattr(invite, "url", "") or "").strip()
            if not invite_url:
                invite_url = f"https://discord.gg/{code}"
            snapshot[code] = {
                "code": code,
                "uses": _safe_int_local(getattr(invite, "uses", 0), 0),
                "inviter_id": inviter_id,
                "inviter_name": inviter_name,
                "invite_url": invite_url,
            }
        return snapshot

    def _resolve_used_invite(
        self,
        before_snapshot: dict[str, dict[str, Any]],
        after_snapshot: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        before = before_snapshot if isinstance(before_snapshot, dict) else {}
        after = after_snapshot if isinstance(after_snapshot, dict) else {}

        selected: dict[str, Any] | None = None
        selected_score = (-1, -1)
        for code, after_row in after.items():
            prev_uses = _safe_int_local((before.get(code) or {}).get("uses"), 0)
            next_uses = _safe_int_local((after_row or {}).get("uses"), 0)
            delta = next_uses - prev_uses
            if delta <= 0:
                continue
            score = (delta, next_uses)
            if score > selected_score:
                selected = dict(after_row or {})
                selected_score = score
        if selected:
            return selected

        for code, after_row in after.items():
            if code in before:
                continue
            next_uses = _safe_int_local((after_row or {}).get("uses"), 0)
            if next_uses <= 0:
                continue
            if selected is None or next_uses > _safe_int_local(selected.get("uses"), 0):
                selected = dict(after_row or {})
        return selected

    def _build_invite_context(
        self,
        *,
        guild: discord.Guild,
        inviter_id: int,
        inviter_name: str,
        invite_code: str,
        invite_url: str,
        inviter_count: int,
    ) -> dict[str, Any]:
        inviter_id = _safe_int_local(inviter_id, 0)
        resolved_name = str(inviter_name or "").strip()
        if inviter_id > 0:
            inviter_member = guild.get_member(inviter_id) if guild else None
            if inviter_member is not None:
                resolved_name = str(
                    getattr(inviter_member, "display_name", None)
                    or getattr(inviter_member, "name", None)
                    or resolved_name
                ).strip()
        if not resolved_name:
            resolved_name = f"User {inviter_id}" if inviter_id > 0 else "Unknown"
        code = str(invite_code or "").strip()
        link = str(invite_url or "").strip()
        if not link and code:
            link = f"https://discord.gg/{code}"
        return {
            "is_known": bool(inviter_id > 0),
            "inviter_id": str(inviter_id) if inviter_id > 0 else "",
            "inviter_name": resolved_name,
            "inviter_mention": f"<@{inviter_id}>" if inviter_id > 0 else "Unknown",
            "inviter_count": max(0, _safe_int_local(inviter_count, 0)),
            "invite_code": code,
            "invite_link": link,
        }

    async def _get_or_store_invite_context(
        self,
        member: discord.Member,
        *,
        used_invite: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        guild_id = int(member.guild.id)
        user_id = int(member.id)
        cache_key = self._invite_context_key(guild_id, user_id)
        cached = self._invite_runtime_context.get(cache_key)
        if isinstance(cached, dict):
            return cached

        row = await invite_members_db.get(guild_id=guild_id, user_id=user_id)
        current_inviter_id = _safe_int_local((row or {}).get("inviter_id"), 0)
        inviter_id = _safe_int_local((used_invite or {}).get("inviter_id"), 0)
        invite_code = str((used_invite or {}).get("code") or "").strip()
        invite_url = str((used_invite or {}).get("invite_url") or "").strip()
        inviter_name = str((used_invite or {}).get("inviter_name") or "").strip()

        if current_inviter_id > 0:
            inviter_id = current_inviter_id
            invite_code = str((row or {}).get("invite_code") or invite_code).strip()
            invite_url = str((row or {}).get("invite_url") or invite_url).strip()
            inviter_name = str((row or {}).get("inviter_name") or inviter_name).strip()

        inviter_count = 0
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        should_increment_stats = bool(inviter_id > 0 and current_inviter_id <= 0)
        if inviter_id > 0:
            stats_row = await invite_stats_db.get(guild_id=guild_id, inviter_id=inviter_id)
            if should_increment_stats:
                next_count = _safe_int_local((stats_row or {}).get("invite_count"), 0) + 1
                if stats_row:
                    await invite_stats_db.update(
                        id=stats_row["id"],
                        invite_count=next_count,
                        last_invited_user_id=user_id,
                        last_invite_code=invite_code or None,
                        last_invite_url=invite_url or None,
                        last_joined_at=now_utc,
                        updated_at=now_utc,
                    )
                else:
                    await invite_stats_db.insert(
                        guild_id=guild_id,
                        inviter_id=inviter_id,
                        invite_count=next_count,
                        last_invited_user_id=user_id,
                        last_invite_code=invite_code or None,
                        last_invite_url=invite_url or None,
                        last_joined_at=now_utc,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                inviter_count = next_count
            else:
                inviter_count = _safe_int_local((stats_row or {}).get("invite_count"), 0)

        inviter_count_at_join = inviter_count
        if inviter_count_at_join <= 0:
            inviter_count_at_join = _safe_int_local((row or {}).get("inviter_count_at_join"), 0)

        if row:
            await invite_members_db.update(
                id=row["id"],
                inviter_id=inviter_id or None,
                inviter_name=inviter_name or None,
                invite_code=invite_code or None,
                invite_url=invite_url or None,
                inviter_count_at_join=inviter_count_at_join,
                updated_at=now_utc,
            )
        else:
            await invite_members_db.insert(
                guild_id=guild_id,
                user_id=user_id,
                inviter_id=inviter_id or None,
                inviter_name=inviter_name or None,
                invite_code=invite_code or None,
                invite_url=invite_url or None,
                inviter_count_at_join=inviter_count_at_join,
                created_at=now_utc,
                updated_at=now_utc,
            )

        context = self._build_invite_context(
            guild=member.guild,
            inviter_id=inviter_id,
            inviter_name=inviter_name,
            invite_code=invite_code,
            invite_url=invite_url,
            inviter_count=inviter_count_at_join,
        )
        self._invite_runtime_context[cache_key] = context
        return context

    async def _track_member_invite(self, member: discord.Member) -> dict[str, Any]:
        guild_key = str(member.guild.id)
        before_snapshot = self._invite_snapshot_cache.get(guild_key)
        if before_snapshot is None:
            before_snapshot = await self._fetch_invite_snapshot(member.guild)
        after_snapshot = await self._fetch_invite_snapshot(member.guild)
        self._invite_snapshot_cache[guild_key] = after_snapshot
        used_invite = self._resolve_used_invite(before_snapshot or {}, after_snapshot or {})
        return await self._get_or_store_invite_context(member, used_invite=used_invite)

    async def _invite_context_for_member(self, member: discord.Member) -> dict[str, Any]:
        cache_key = self._invite_context_key(member.guild.id, member.id)
        cached = self._invite_runtime_context.get(cache_key)
        if isinstance(cached, dict):
            return cached
        return await self._get_or_store_invite_context(member, used_invite=None)

    @staticmethod
    def _invite_tokens_from_context(context: dict[str, Any]) -> dict[str, Any]:
        data = context if isinstance(context, dict) else {}
        inviter_id_text = str(data.get("inviter_id") or "").strip()
        inviter_count = _safe_int_local(data.get("inviter_count"), 0)
        invite_link = str(data.get("invite_link") or "").strip()
        invite_code = str(data.get("invite_code") or "").strip()
        return {
            "inviter": str(data.get("inviter_name") or "Unknown"),
            "inviter.id": inviter_id_text,
            "inviter.mention": str(data.get("inviter_mention") or "Unknown"),
            "inviter.count": str(inviter_count),
            "invite.code": invite_code,
            "invite.link": invite_link,
            "invite.url": invite_link,
        }

    async def _build_invite_notice_text(
        self,
        *,
        welcomer_cache: dict[str, Any],
        member: discord.Member,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel,
        invite_context: dict[str, Any],
    ) -> str:
        if not bool((welcomer_cache or {}).get("invite_welcome_enabled")):
            return ""
        known_template = (
            str((welcomer_cache or {}).get("invite_welcome_template") or "").strip()
            or "สมาชิกคนนี้มาด้วยคำเชิญของ {inviter.mention} • เชิญแล้ว {inviter.count} คน"
        )
        unknown_template = (
            str((welcomer_cache or {}).get("invite_welcome_unknown_template") or "").strip()
            or "ไม่สามารถตรวจสอบได้ว่าเข้ามาจากคำเชิญของใคร"
        )
        source_template = known_template if bool((invite_context or {}).get("is_known")) else unknown_template
        if not source_template:
            return ""
        rendered = fetch_variables(
            text=source_template,
            member=member,
            guild=guild,
            channel=channel,
            extra=self._invite_tokens_from_context(invite_context),
        )
        return str(rendered or "").strip()

    async def _apply_extra_protection_action(
        self,
        *,
        guild: discord.Guild,
        target: discord.Member,
        action: str,
        timeout_seconds: int,
        reason: str,
    ) -> None:
        normalized_action = str(action or "warn").strip().lower()
        if normalized_action == "none":
            return
        if normalized_action == "warn":
            try:
                await target.send(
                    embed=discord.Embed(
                        title="Extra Protection Warning",
                        description=f"Guild: **{guild.name}**\nReason: **{reason}**",
                        color=color.orange,
                    )
                )
            except Exception:
                pass
            return
        if normalized_action == "mute":
            try:
                await target.timeout(
                    datetime.timedelta(seconds=max(30, int(timeout_seconds or 300))),
                    reason=f"Extra Protection: {reason}",
                )
            except Exception as error:
                logger.warning(f"ExtraProtection mute failed in {guild.name}: {error}")
            return
        if normalized_action == "kick":
            try:
                await guild.kick(target, reason=f"Extra Protection: {reason}")
            except Exception as error:
                logger.warning(f"ExtraProtection kick failed in {guild.name}: {error}")
            return
        if normalized_action == "ban":
            try:
                await guild.ban(target, reason=f"Extra Protection: {reason}")
            except Exception as error:
                logger.warning(f"ExtraProtection ban failed in {guild.name}: {error}")

    async def join_log(self,member:discord.Member):
        try:
            guilds_log_cache = cache.guilds_log.get(str(member.guild.id))
            if not guilds_log_cache:
                return
            if not guilds_log_cache.get('enabled'):
                return logger.debug(f"Guild {member.guild.name} has logging disabled")
            channel_id = guilds_log_cache.get('member_join_channel_id')
            if not channel_id:
                return logger.debug(f"Channel ID not found for member join log in {member.guild.name}")
            
            embed = discord.Embed(
                title=f'{member.display_name} has joined the server',
                description=f'**__User__** {member.mention}\n**__Username:__** {member.name}\n**__User ID:__** {member.id}\n\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>',
                color=color.green
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f'User ID: {member.id}')
            await self.bot.log.send(guild=member.guild,embed=embed,type=f"member_join_channel_id")
        except Exception as e:
            logger.error(f"Error in on_member_join.join_log: {e}")

    async def invite_tracking_module(self, member: discord.Member):
        if member.bot:
            return
        welcomer_cache = self.bot.cache.welcomer_settings.get(str(member.guild.id), {}) or {}
        tracking_enabled = bool(welcomer_cache.get("invite_tracking_enabled"))
        invite_notice_enabled = bool(welcomer_cache.get("invite_welcome_enabled"))
        if not tracking_enabled and not invite_notice_enabled:
            return
        try:
            await self._track_member_invite(member)
        except Exception as error:
            logger.warning(f"Invite tracking failed in {member.guild.name} for {member.id}: {error}")

    async def welcome_pipeline_module(self, member: discord.Member):
        try:
            await self.invite_tracking_module(member)
        except Exception:
            pass
        await self.guild_welcome_module(member)

    async def _bootstrap_invite_snapshots(self) -> None:
        for guild in list(getattr(self.bot, "guilds", []) or []):
            try:
                snapshot = await self._fetch_invite_snapshot(guild)
                self._invite_snapshot_cache[str(guild.id)] = snapshot
            except Exception:
                continue

    @commands.Cog.listener()
    async def on_ready(self):
        if self._invite_snapshot_bootstrapped:
            return
        self._invite_snapshot_bootstrapped = True
        if self._invite_snapshot_task and not self._invite_snapshot_task.done():
            return
        self._invite_snapshot_task = asyncio.create_task(
            self._bootstrap_invite_snapshots(),
            name="invite_snapshot_bootstrap",
        )

    add_bot_timeouts = {}
    async def anti_bot_add_module(self,bot:discord.Member):
        if not bot.bot:
            return logger.warning(f"User {bot} is not a bot")
        if self._is_system_trusted_bot(bot.id):
            return logger.info(
                f"Skip anti bot add for system-trusted bot {bot.id} in {bot.guild.name}"
            )
        if self._is_preexisting_member_from_restart(bot):
            return logger.info(
                f"Skip anti bot add for pre-existing bot {bot.id} in {bot.guild.name} (restart safety)"
            )
        try:
            anti_nuke_cache = self.bot.cache.antinuke_settings.get(str(bot.guild.id))
            if not anti_nuke_cache:
                return 
            if not anti_nuke_cache.get('enabled'):
                return
            if not anti_nuke_cache.get('anti_bot_add'):
                return logger.warning(f"Guild {bot.guild.name} has anti bot add disabled")
            armed_at_ts = _coerce_unix_ts_local(anti_nuke_cache.get("anti_bot_add_armed_at_ts"))
            if armed_at_ts <= 0:
                armed_at_ts = _coerce_unix_ts_local(anti_nuke_cache.get("created_at"))
            bot_joined_at_ts = self._member_joined_at_ts(bot)
            if armed_at_ts > 0 and bot_joined_at_ts > 0 and bot_joined_at_ts < armed_at_ts:
                return logger.info(
                    f"Skip anti bot add for existing bot {bot.id} in {bot.guild.name} (joined before arm)"
                )
            
            async def check_entry():
                async for entry in bot.guild.audit_logs(limit=1,action=discord.AuditLogAction.bot_add,after=datetime.datetime.now()-datetime.timedelta(seconds=5)):
                    if entry.target.id == bot.id:
                        return entry
            entry = await check_entry()
            if entry:
                entry_created_at_ts = _coerce_unix_ts_local(getattr(entry, "created_at", None))
                if armed_at_ts > 0 and entry_created_at_ts > 0 and entry_created_at_ts < armed_at_ts:
                    return logger.info(
                        f"Skip anti bot add for {bot.id} in {bot.guild.name}: audit entry before armed time"
                    )
                bot_start_ts = self._bot_start_ts()
                if (
                    bot_start_ts > 0
                    and entry_created_at_ts > 0
                    and entry_created_at_ts <= (bot_start_ts + self._BOT_ADD_STARTUP_GRACE_SECONDS)
                ):
                    return logger.info(
                        f"Skip anti bot add for {bot.id} in {bot.guild.name}: startup grace window"
                    )
                adder = entry.user
                if adder == self.bot.user:
                    return logger.warning(f"Bot {bot} was added by the bot")
                if getattr(adder, "bot", False):
                    return logger.info(
                        f"Skip anti bot add for {bot.id} in {bot.guild.name}: adder is a bot/system user"
                    )
            else:
                return logger.warning(f"Bot {bot} was not added by a user or maybe unknown user")
            
            anti_nuke_bypass_cache = self.bot.cache.antinuke_bypass.get(str(bot.guild.id),{}).get(str(adder.id),{})
            if anti_nuke_bypass_cache.get('anti_bot_add'):
                return logger.warning(f"User {adder} is bypassed from anti bot add")
            
            if adder.id == bot.guild.owner.id or await checks.check_is_owner_raw(adder,bot.guild):
                return logger.warning(f"Bot {bot} was added by the owner")
            if adder.top_role.position >= bot.guild.me.top_role.position:
                return logger.warning(f"Bot {bot} was added by a user with a higher role than the bot")
            
            # ==================================
            if str(bot.guild.id) not in self.add_bot_timeouts:
                self.add_bot_timeouts[str(bot.guild.id)] = {}
            if str(adder.id) not in self.add_bot_timeouts.get(str(bot.guild.id)):
                self.add_bot_timeouts[str(bot.guild.id)][str(adder.id)] = {
                    'count': 0,
                    'created_at': datetime.datetime.now()
                }
            self.add_bot_timeouts[str(bot.guild.id)][str(adder.id)]['count'] += 1
            self.add_bot_timeouts[str(bot.guild.id)][str(adder.id)]['created_at'] = datetime.datetime.now()

            if str(bot.guild.id) in self.add_bot_timeouts:
                if self.add_bot_timeouts.get(str(bot.guild.id)):
                    if self.add_bot_timeouts.get(str(bot.guild.id),{}).get(str(adder.id)):
                        if (self.add_bot_timeouts.get(str(bot.guild.id),{}).get(str(adder.id),{}).get('count') >= anti_nuke_cache.get('anti_bot_add_limit',1)
                            and
                            self.add_bot_timeouts.get(str(bot.guild.id),{}).get(str(adder.id),{}).get('created_at') >= (datetime.datetime.now() - datetime.timedelta(seconds=60))
                            ):
                            # getting action for the user
                            action = anti_nuke_cache.get('anti_bot_add_punishment')

                            async def send_notify_to_user(user:discord.Member,embed:discord.Embed):
                                try:
                                    await user.send(embed=embed)
                                except Exception:
                                    logger.warning(f"Could not send message to {user} in {bot.guild.name}")

                            if action == 'ban':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{bot.guild.name}`**\n**__Action:__** `Ban`\n**__Reason:__** Anti Bot Add\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=bot.guild.icon.url if bot.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(adder,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {adder.mention}\n**__ID__**: `{adder.id}`\n**__Action__**: `Ban`\n**__Reason__**: Anti Bot Add\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=adder.display_avatar.url)
                                    await bot.guild.ban(adder,reason="Banned by Antinuke System: Anti Bot Add")
                                    await self.bot.antinuke_log.send(guild=bot.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_bot_add_module: {e}")
                            elif action == 'kick':
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__Guild:__ `{bot.guild.name}`**\n**__Action:__** `Kick`\n**__Reason:__** Anti Bot Add\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=bot.guild.icon.url if bot.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(adder,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="ระบบป้องกันอัโนมัิ",
                                        description=f"**__User__**: {adder.mention}\n**__ID__**: `{adder.id}`\n**__Action__**: `Kick`\n**__Reason__**: Anti Bot Add\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=adder.display_avatar.url)
                                    await bot.guild.kick(adder,reason="Kicked by Antinuke System: Anti Bot Add")
                                    await self.bot.antinuke_log.send(guild=bot.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_bot_add_module: {e}")
                            elif action == 'warn':
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__Guild:__ `{bot.guild.name}`**\n**Details:** ```\nคุณได้รับคำเตือนจากระบบ: Anti Bot Add\nกรุณาอย่าทำซ้ำอีก\n```\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=bot.guild.icon.url if bot.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(adder,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="คำเตือนระบบป้องกัน",
                                        description=f"**__User__**: {adder.mention}\n**__ID__**: `{adder.id}`\n**__Action__**: `Warn`\n**__Reason__**: Anti Bot Add\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=adder.display_avatar.url)
                                    await self.bot.antinuke_log.send(guild=bot.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_bot_add_module: {e}")
                            elif action == 'mute':
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__Guild:__ `{bot.guild.name}`**\n**__Action:__** `Mute`\n**__Reason:__** Anti Bot Add\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=bot.guild.icon.url if bot.guild.icon else None)
                                    asyncio.create_task(send_notify_to_user(adder,embed))
                                except Exception:
                                    pass
                                try:
                                    embed = discord.Embed(
                                        title="จำกัดสิทธิ์โดยระบบป้องกัน",
                                        description=f"**__User__**: {adder.mention}\n**__ID__**: `{adder.id}`\n**__Action__**: `Mute`\n**__Reason__**: Anti Bot Add\n**__Time__**: <t:{int(datetime.datetime.now().timestamp())}:R>",
                                        color=color.red
                                    )
                                    embed.set_footer(text=f"Antinuke System",icon_url=self.bot.user.display_avatar.url)
                                    embed.set_thumbnail(url=adder.display_avatar.url)
                                    try:
                                        await adder.edit(roles=[],reason="Muted by Antinuke System: Anti Bot Add")
                                    except Exception:
                                        pass
                                    await adder.timeout(datetime.timedelta(days=1),reason="Muted by Antinuke System: Anti Bot Add")
                                    await self.bot.antinuke_log.send(guild=bot.guild,embed=embed,type="antinuke")
                                except Exception as e:
                                    logger.error(f"Error in on_member_remove.anti_bot_add_module: {e}")
                            else:
                                return logger.warning(f"การดำเนินการไม่ถูกต้อง {action} in {bot.guild.name}")
                            
                            if action != 'warn':
                            # reset the timeout
                                if str(bot.guild.id) in self.add_bot_timeouts:
                                    if str(adder.id) in self.add_bot_timeouts.get(str(bot.guild.id)):
                                        self.add_bot_timeouts[str(bot.guild.id)][str(adder.id)] = {
                                            'count': 0,
                                            'created_at': datetime.datetime.now()
                                        }
                            return
                        
        except Exception as e:
            logger.error(f"Error in on_member_remove.anti_bot_add_module: {e}")

    async def extra_protection_bot_add_module(self, bot: discord.Member):
        if not bot.bot:
            return
        guild = bot.guild
        if self._is_preexisting_member_from_restart(bot):
            return logger.info(
                f"Skip extra protection bot-add for pre-existing bot {bot.id} in {guild.name} (restart safety)"
            )
        try:
            settings = await self._get_extra_protection_settings(guild.id)
            if not settings.get("enabled"):
                return
            if not settings.get("block_bot_add_enabled"):
                return
            armed_at_ts = _coerce_unix_ts_local(settings.get("block_bot_add_armed_at_ts"))
            if armed_at_ts <= 0:
                await self._arm_extra_protection_bot_add(guild.id, settings)
                return
            bot_joined_at_ts = self._member_joined_at_ts(bot)
            if bot_joined_at_ts > 0 and bot_joined_at_ts < armed_at_ts:
                return logger.info(
                    f"Skip extra protection bot-add for existing bot {bot.id} in {guild.name} (joined before arm)"
                )

            async def _find_bot_add_entry():
                async for entry in guild.audit_logs(
                    limit=4,
                    action=discord.AuditLogAction.bot_add,
                    after=datetime.datetime.now() - datetime.timedelta(seconds=20),
                ):
                    target_id = str(getattr(getattr(entry, "target", None), "id", "") or "")
                    if target_id and target_id == str(bot.id):
                        return entry
                return None

            entry = await _find_bot_add_entry()
            if not entry:
                return
            entry_created_at_ts = _coerce_unix_ts_local(getattr(entry, "created_at", None))
            if armed_at_ts > 0 and entry_created_at_ts > 0 and entry_created_at_ts < armed_at_ts:
                return logger.info(
                    f"Skip extra protection bot-add for {bot.id} in {guild.name}: audit entry before armed time"
                )
            bot_start_ts = self._bot_start_ts()
            if (
                bot_start_ts > 0
                and entry_created_at_ts > 0
                and entry_created_at_ts <= (bot_start_ts + self._BOT_ADD_STARTUP_GRACE_SECONDS)
            ):
                return logger.info(
                    f"Skip extra protection bot-add for {bot.id} in {guild.name}: startup grace window"
                )
            adder = getattr(entry, "user", None)
            if not adder or adder == self.bot.user:
                return
            if getattr(adder, "bot", False):
                return
            if str(adder.id) in set(settings.get("bot_add_whitelist_user_ids", [])):
                return
            trusted_bot_ids = set(settings.get("bot_add_whitelist_bot_ids", []))
            trusted_bot_ids.update(self._system_trusted_bot_ids)
            if str(bot.id) in trusted_bot_ids:
                return
            if guild.owner_id == adder.id or await checks.check_is_owner_raw(adder, guild):
                return

            me = guild.me
            if me and guild.get_member(bot.id) is not None and me.guild_permissions.kick_members:
                try:
                    await guild.kick(bot, reason="Blocked by Extra Protection (bot add)")
                except Exception as error:
                    logger.warning(f"ExtraProtection could not remove bot {bot} in {guild.name}: {error}")

            adder_member = guild.get_member(adder.id)
            if adder_member is None:
                return
            await self._apply_extra_protection_action(
                guild=guild,
                target=adder_member,
                action=str(settings.get("delete_action") or "warn"),
                timeout_seconds=int(settings.get("timeout_seconds") or 300),
                reason=f"Unauthorized bot add ({bot.id})",
            )
        except Exception as error:
            logger.error(f"Error in on_member_join.extra_protection_bot_add_module: {error}")

    async def guild_welcome_module(self,member:discord.Member):
        guild = member.guild
        try:
            welcomer_cache = self.bot.cache.welcomer_settings.get(str(guild.id),{})
            if not welcomer_cache:
                return
            if not welcomer_cache.get('welcome'):
                return logger.warning(f"Guild {guild.name} has welcome disabled")
            guild_data = cache.guilds.get(str(guild.id), {}) or {}
            can_use_image_cards = _plan_at_least(guild_data.get("subscription", "free"), "silver")
            send_welcome_image = bool(welcomer_cache.get("welcome_image")) and can_use_image_cards

            if not welcomer_cache.get('welcome_message') and not welcomer_cache.get('welcome_embed') and not send_welcome_image:
                return logger.warning(f"Guild {guild.name} has welcome message/embed/image disabled")
            channel_id = welcomer_cache.get('welcome_channel')
            if not channel_id:
                return logger.warning(f"Channel ID not found for welcome in {guild.name}")
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return logger.warning(f"Channel not found for welcome in {guild.name}")
            me = guild.me
            if me:
                perms = channel.permissions_for(me)
                if not perms.send_messages:
                    return logger.warning(f"Bot missing send_messages permission in welcome channel for {guild.name}")
                if welcomer_cache.get('welcome_embed') and not perms.embed_links:
                    return logger.warning(f"Bot missing embed_links permission in welcome channel for {guild.name}")
                if send_welcome_image and not perms.attach_files:
                    return logger.warning(f"Bot missing attach_files permission in welcome channel for {guild.name}")

            invite_context = await self._invite_context_for_member(member)
            invite_tokens = self._invite_tokens_from_context(invite_context)

            if welcomer_cache.get('welcome_message'):
                message_content = fetch_variables(
                    text=welcomer_cache.get('welcome_message_content'),
                    member=member,
                    guild=guild,
                    channel=channel,
                    extra=invite_tokens,
                )
            else:
                message_content = None

            embed_color = discord.Color.blurple()
            if welcomer_cache.get('welcome_embed_color'):
                if str(welcomer_cache.get('welcome_embed_color')).lower() == 'red':
                    embed_color = color.red
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'green':
                    embed_color = color.green
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'blue':
                    embed_color = color.blue
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'yellow':
                    embed_color = color.yellow
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'purple':
                    embed_color = color.purple
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'orange':
                    embed_color = color.orange
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'pink':
                    embed_color = color.pink
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'cyan':
                    embed_color = color.black
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'white':
                    embed_color = color.white
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'black':
                    embed_color = color.black
                elif str(welcomer_cache.get('welcome_embed_color')).lower() == 'gray':
                    embed_color = color.gray
                else:
                    embed_color = discord.Color.blurple()


            
            if welcomer_cache.get('welcome_embed'):
                embed_title = fetch_variables(
                    text=welcomer_cache.get('welcome_embed_title'),
                    member=member,
                    guild=guild,
                    channel=channel,
                    extra=invite_tokens,
                )
                embed_description = fetch_variables(
                    text=welcomer_cache.get('welcome_embed_description'),
                    member=member,
                    guild=guild,
                    channel=channel,
                    extra=invite_tokens,
                )
                if not str(embed_title or '').strip() and not str(embed_description or '').strip():
                    embed_description = f"ยินดีต้อนรับ {member.mention} สู่ {guild.name}"
                embed = discord.Embed(
                    title=embed_title,
                    description=embed_description,
                    color=embed_color
                )
                if welcomer_cache.get('welcome_embed_thumbnail'):
                    embed.set_thumbnail(
                        url=fetch_variables(
                            text=welcomer_cache.get('welcome_embed_thumbnail'),
                            member=member,
                            guild=guild,
                            channel=channel,
                            extra=invite_tokens,
                        )
                    )
                if welcomer_cache.get('welcome_embed_image'):
                    embed.set_image(
                        url=fetch_variables(
                            text=welcomer_cache.get('welcome_embed_image'),
                            member=member,
                            guild=guild,
                            channel=channel,
                            extra=invite_tokens,
                        )
                    )
                if welcomer_cache.get('welcome_embed_footer'):
                    embed.set_footer(
                        text=fetch_variables(
                            text=welcomer_cache.get('welcome_embed_footer'),
                            member=member,
                            guild=guild,
                            channel=channel,
                            extra=invite_tokens,
                        ),
                        icon_url=fetch_variables(
                            text=welcomer_cache.get('welcome_embed_footer_icon'),
                            member=member,
                            guild=guild,
                            channel=channel,
                            extra=invite_tokens,
                        )
                    )
                if welcomer_cache.get('welcome_embed_author'):
                    embed.set_author(
                        name=fetch_variables(
                            text=welcomer_cache.get('welcome_embed_author'),
                            member=member,
                            guild=guild,
                            channel=channel,
                            extra=invite_tokens,
                        ),
                        icon_url=fetch_variables(
                            text=welcomer_cache.get('welcome_embed_author_icon'),
                            member=member,
                            guild=guild,
                            channel=channel,
                            extra=invite_tokens,
                        ),
                        url=fetch_variables(
                            text=welcomer_cache.get('welcome_embed_author_url'),
                            member=member,
                            guild=guild,
                            channel=channel,
                            extra=invite_tokens,
                        )
                    )
            else:
                embed = None

            image_file = None
            if send_welcome_image:
                top_text = fetch_variables(
                    text=welcomer_cache.get("welcome_image_top_text") or "ยินดีต้อนรับ {user}",
                    member=member,
                    guild=guild,
                    channel=channel,
                    extra=invite_tokens,
                ) or f"ยินดีต้อนรับ {member.display_name}"
                bottom_text = fetch_variables(
                    text=welcomer_cache.get("welcome_image_bottom_text") or "เข้าสู่ {server}",
                    member=member,
                    guild=guild,
                    channel=channel,
                    extra=invite_tokens,
                ) or f"เข้าสู่ {guild.name}"
                card_bytes = build_member_notice_card(
                    avatar_url=str(member.display_avatar.url),
                    top_text=top_text,
                    bottom_text=bottom_text,
                    theme_key=welcomer_cache.get("welcome_image_theme", "music"),
                    theme_url=welcomer_cache.get("welcome_image_theme_url"),
                    user_theme_url=str(member.display_avatar.url),
                    guild_theme_url=str(getattr(getattr(guild, "icon", None), "url", "") or ""),
                    layout_mode=welcomer_cache.get("welcome_image_layout_mode", "center_stack"),
                    avatar_position=welcomer_cache.get("welcome_image_avatar_position", "center"),
                    text_align=welcomer_cache.get("welcome_image_text_align", "center"),
                    font_style=welcomer_cache.get("welcome_image_font_style", "classic"),
                )
                if card_bytes is not None:
                    image_file = discord.File(card_bytes, filename="welcome-card.png")
                    if embed and not welcomer_cache.get("welcome_embed_image"):
                        embed.set_image(url="attachment://welcome-card.png")

            invite_notice_text = await self._build_invite_notice_text(
                welcomer_cache=welcomer_cache,
                member=member,
                guild=guild,
                channel=channel,
                invite_context=invite_context,
            )
            if invite_notice_text:
                if message_content:
                    message_content = f"{message_content}\n{invite_notice_text}".strip()
                elif embed is not None:
                    current_description = str(getattr(embed, "description", "") or "").strip()
                    if current_description:
                        combined = f"{current_description}\n{invite_notice_text}".strip()
                        if len(combined) <= 4096:
                            embed.description = combined
                        else:
                            embed.add_field(name="Invite", value=invite_notice_text[:1024], inline=False)
                    else:
                        embed.description = invite_notice_text[:4096]

            if not message_content and embed is None and image_file is None:
                return
            try:
                send_payload = {}
                if message_content:
                    send_payload["content"] = message_content
                if embed is not None:
                    send_payload["embed"] = embed
                if image_file is not None:
                    send_payload["file"] = image_file
                await channel.send(**send_payload)
            except discord.Forbidden:
                logger.warning(f"Missing permissions to send welcome message in {guild.name}")
            except Exception as send_error:
                logger.error(f"Error in on_member_join.guild_welcome_module.send: {send_error}")
        except Exception as e:
            logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    async def guild_autorole_module(self,member:discord.Member):
        guild = member.guild
        try:
            welcomer_cache = self.bot.cache.welcomer_settings.get(str(guild.id),{})
            if not welcomer_cache:
                return
            if not welcomer_cache.get('autorole'):
                return logger.info(f"Guild {guild.name} has autorole disabled")
            
            autoroles = _parse_id_list(welcomer_cache.get('autoroles','[]'))
            if not autoroles:
                return logger.info(f"Guild {guild.name} has no autoroles")
            
            roles_to_add = []
            for role in autoroles:
                role = guild.get_role(int(role))
                if role:
                    if role.permissions.administrator:
                        logger.warning(f"Role {role.name} in {guild.name} is an admin role")
                        continue
                    roles_to_add.append(role)
            if not roles_to_add:
                return logger.info(f"Guild {guild.name} has no valid autoroles")
            if self._member_left_guild(member):
                return logger.info(f"Skip autorole in {guild.name}: member {member.id} already left")
            
            try:
                await member.add_roles(*roles_to_add,reason="Autoroles by Welcomer System")
            except discord.Forbidden:
                logger.warning(f"Missing permissions to add autoroles in {guild.name}")
            except discord.NotFound:
                logger.info(f"Skip autorole in {guild.name}: member {member.id} not found")
            except Exception as role_error:
                logger.error(f"Error in on_member_join.guild_autorole_module.add_roles: {role_error}")
        except Exception as e:
            logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    async def guild_autonick_module(self,member:discord.Member):
        guild = member.guild
        try:
            welcomer_cache = self.bot.cache.welcomer_settings.get(str(guild.id),{})
            if not welcomer_cache:
                return
            if not welcomer_cache.get('autonick'):
                return logger.info(f"Guild {guild.name} has autonick disabled")
            
            autonick_format = welcomer_cache.get('autonick_format')
            if not autonick_format:
                return logger.info(f"Guild {guild.name} has no autonick format")
            
            autonick_format = fetch_variables(text=autonick_format,member=member,guild=guild)
            if self._member_left_guild(member):
                return logger.info(f"Skip autonick in {guild.name}: member {member.id} already left")
            try:
                await member.edit(nick=autonick_format,reason="Autonick by Welcomer System")
            except discord.Forbidden:
                logger.warning(f"Missing permissions to change nickname in {guild.name}")
            except discord.NotFound:
                logger.info(f"Skip autonick in {guild.name}: member {member.id} not found")
            except Exception as nick_error:
                logger.error(f"Error in on_member_join.guild_autonick_module.edit: {nick_error}")
        except Exception as e:
            logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
    
    async def guild_greet_module(self,member:discord.Member):
        guild = member.guild
        try:
            welcomer_cache = self.bot.cache.welcomer_settings.get(str(guild.id),{})
            if not welcomer_cache:
                return
            if not welcomer_cache.get('greet'):
                return logger.info(f"Guild {member.guild.name} has greeting disabled")
            channel_ids = _parse_id_list(welcomer_cache.get('greet_channels','[]'))
            if not channel_ids:
                return logger.warning(f"Channel ID not found for greeting in {member.guild.name}")
            for channel_id in channel_ids:
                try:
                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        logger.warning(f"Channel not found for greeting in {member.guild.name}")
                        continue
                    me = guild.me
                    if me and not channel.permissions_for(me).send_messages:
                        logger.warning(f"Bot missing send_messages permission in greet channel for {guild.name}")
                        continue
                    message_content = fetch_variables(
                        text=welcomer_cache.get('greet_message'),
                        member=member,
                        guild=guild,
                        channel=channel
                    )
                    if message_content:
                        try:
                            await channel.send(content=message_content,delete_after=welcomer_cache.get('greet_delete_after',5))
                        except discord.Forbidden:
                            logger.warning(f"Missing permissions to send greet message in {guild.name}")
                            continue
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error in on_member_join.guild_greet_module: {e}")
        except Exception as e:
            logger.error(f"Error in on_member_join.guild_greet_module: {e}")


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            asyncio.create_task(
                dashboard_activity.record_join(
                    member.guild.id,
                    member_count=int(getattr(member.guild, "member_count", 0) or 0),
                )
            )
        except Exception:
            pass
        try:
            asyncio.create_task(self.anti_bot_add_module(member))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.extra_protection_bot_add_module(member))
        except Exception:
            pass
        try:
            asyncio.create_task(self.join_log(member))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.welcome_pipeline_module(member))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.guild_autorole_module(member))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.guild_autonick_module(member))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.guild_greet_module(member))
        except Exception as e:
            pass
