import discord
import asyncio
import datetime

from skylinebot.engine.bot_runtime import AutoShardedBot
import storage.afk
from skylinebot.console.logging import logger

from skylinebot.memory.cache import cache

from skylinebot.workflows.subscription_actions import (
    _sync_guild_bot_nickname,
    change_guild_subscription,
    change_user_subscription,
)
from skylinebot.workflows.billing import is_billing_managed_guild
from skylinebot.workflows.afk_delay import afk_delay

import json

import storage


def _safe_json_list(raw_value) -> list:
    if isinstance(raw_value, list):
        return raw_value
    if raw_value is None:
        return []
    try:
        value = json.loads(str(raw_value))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _coerce_expiry_datetime(raw_value) -> datetime.datetime | None:
    if not raw_value:
        return None

    dt_value: datetime.datetime | None = None
    if isinstance(raw_value, datetime.datetime):
        dt_value = raw_value
    elif isinstance(raw_value, (int, float)):
        try:
            ts_value = float(raw_value)
            if ts_value > 10_000_000_000:
                ts_value /= 1000.0
            dt_value = datetime.datetime.fromtimestamp(ts_value, tz=datetime.timezone.utc)
        except Exception:
            dt_value = None
    else:
        text_value = str(raw_value).strip()
        if not text_value:
            return None
        try:
            if text_value.isdigit():
                ts_value = float(text_value)
                if ts_value > 10_000_000_000:
                    ts_value /= 1000.0
                dt_value = datetime.datetime.fromtimestamp(ts_value, tz=datetime.timezone.utc)
            else:
                dt_value = datetime.datetime.fromisoformat(text_value.replace("Z", "+00:00"))
        except Exception:
            dt_value = None

    if dt_value is None:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=datetime.timezone.utc)
    return dt_value.astimezone(datetime.timezone.utc)


check_guilds_subscription_running = False
_guild_subscription_reminder_sent_at: dict[str, datetime.datetime] = {}
_guild_subscription_reminder_cooldown = datetime.timedelta(hours=18)
async def check_guilds_subscription(bot: AutoShardedBot):
    global check_guilds_subscription_running
    if check_guilds_subscription_running:
        return logger.warning("ระบบตรวจสอบพรีเมียมกิลด์กำลังทำงานอยู่แล้ว")
    check_guilds_subscription_running = True
    while not bot.is_ready():
        await asyncio.sleep(1)
    # logger.info("Checking Subscriptions")
    while True:
        now_utc = _utc_now()
        for guild_id, data in list(cache.guilds.items()):
            try:
                guild_id_text = str(guild_id)
                subscription_code = str(data.get("subscription") or "free").strip().lower()
                try:
                    await _sync_guild_bot_nickname(
                        bot=bot,
                        guild_id=int(guild_id),
                        subscription_code=subscription_code,
                    )
                except Exception:
                    pass
                if subscription_code == "free":
                    _guild_subscription_reminder_sent_at.pop(guild_id_text, None)
                    continue

                subscription_end_dt = _coerce_expiry_datetime(data.get("subscription_end"))
                if not subscription_end_dt:
                    continue

                remaining = subscription_end_dt - now_utc
                if datetime.timedelta(0) < remaining <= datetime.timedelta(days=3):
                    last_reminder_at = _guild_subscription_reminder_sent_at.get(guild_id_text)
                    if not last_reminder_at or (now_utc - last_reminder_at) >= _guild_subscription_reminder_cooldown:
                        logger.info(f"Subscription ending soon for guild {guild_id}")
                        try:
                            guild = bot.get_guild(int(guild_id)) or await bot.fetch_guild(int(guild_id))
                            if guild:
                                guild_cache = cache.guilds.get(str(guild.id), {})
                                owners = []

                                if getattr(guild, "owner", None):
                                    owners.append(guild.owner)

                                guild_owner_id = getattr(guild, "owner_id", None)
                                if guild_owner_id:
                                    owner_from_id = bot.get_user(int(guild_owner_id))
                                    if not owner_from_id:
                                        try:
                                            owner_from_id = await bot.fetch_user(int(guild_owner_id))
                                        except Exception:
                                            owner_from_id = None
                                    if owner_from_id:
                                        owners.append(owner_from_id)

                                for extra_owner_id in _safe_json_list(guild_cache.get("extra_owner_ids", "[]")):
                                    try:
                                        extra_owner_id = int(extra_owner_id)
                                    except (TypeError, ValueError):
                                        continue
                                    owner = bot.get_user(extra_owner_id)
                                    if not owner:
                                        try:
                                            owner = await bot.fetch_user(extra_owner_id)
                                        except Exception:
                                            owner = None
                                    if owner:
                                        owners.append(owner)

                                dedup_owners = []
                                seen_owner_ids = set()
                                for owner in owners:
                                    owner_id = getattr(owner, "id", None)
                                    if not owner_id or owner_id in seen_owner_ids:
                                        continue
                                    seen_owner_ids.add(owner_id)
                                    dedup_owners.append(owner)

                                if dedup_owners:
                                    for owner in dedup_owners:
                                        try:
                                            await owner.send(f"Your subscription for {guild.name} is ending in less than 3 days, please renew it.")
                                        except Exception:
                                            logger.error(f"Error sending message to owner of guild {guild_id} - {getattr(owner, 'id', 'unknown')}")
                                else:
                                    logger.warning(f"No reachable owner found for guild {guild_id}; skip subscription reminder")
                            else:
                                logger.error(f"Guild {guild_id} not found")
                        except Exception as e:
                            logger.warning(f"Error sending message to owner of guild {guild_id}: {e}")
                        finally:
                            _guild_subscription_reminder_sent_at[guild_id_text] = now_utc

                if remaining.total_seconds() > 0:
                    continue

                try:
                    if await is_billing_managed_guild(int(guild_id)):
                        # Billing scheduler handles grace period, auto-renew and downgrade timing.
                        continue
                except Exception:
                    pass

                logger.warning(f"Subscription ended for guild {guild_id}")
                await change_guild_subscription(
                    bot=bot,
                    guild_id=int(guild_id),
                    subscription="free",
                    valid_for_days=None,
                )
                _guild_subscription_reminder_sent_at.pop(guild_id_text, None)
            except Exception as e:
                logger.warning(f"Error while checking subscription for guild {guild_id}: {e}")
        await asyncio.sleep(60)

check_users_subscription_running = False
async def check_users_subscription(bot: AutoShardedBot):
    global check_users_subscription_running
    if check_users_subscription_running:
        return logger.warning("ระบบตรวจสอบพรีเมียมผู้ใช้กำลังทำงานอยู่แล้ว")
    check_users_subscription_running = True
    while not bot.is_ready():
        await asyncio.sleep(1)
    # logger.info("Checking Subscriptions")
    while True:
        for user_id,data in cache.users.items():
            if data.get('subscription') == 'free':
                continue
            if not data.get('no_prefix_subscription'):
                continue
                
            if not data.get('no_prefix_end'):
                # logger.info(f"Infinite subscription found for user {user_id}")
                continue
            
            # if subscription has less than 3 days left notify the owner
            if data.get('no_prefix_end',datetime.datetime.now()).astimezone() < datetime.datetime.now().astimezone() + datetime.timedelta(days=3):
                logger.info(f"Subscription ending soon for user {user_id}")
                try:
                    user = bot.get_user(int(user_id))
                    if user:
                        await user.send(f"Your subscription is ending soon, please renew it.")
                    else:
                        logger.error(f"User {user_id} not found")
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")

            if data.get('no_prefix_end',datetime.datetime.now()).astimezone() > datetime.datetime.now().astimezone():
                # logger.info(f"Subscription has not ended for user {user_id}")
                continue
            
            logger.info(f"Subscription ended for user {user_id}")

            await change_user_subscription(
                bot=bot,
                user_id=int(user_id),
                subscription=None,
                valid_for_days=None
            )
        
        # 12 hours
        await asyncio.sleep(12*60*60)

restart_afk_functions_running = False
async def resume_afk_functions(bot: AutoShardedBot):
    global restart_afk_functions_running
    if restart_afk_functions_running:
        return logger.warning("ระบบ AFK กำลังถูกกู้คืนอยู่แล้ว")
    restart_afk_functions_running = True
    while not bot.is_ready():
        await asyncio.sleep(1)
    all_afk_data = await storage.afk.get_all()
    for afk_data in all_afk_data:
        asyncio.create_task(afk_delay(bot=bot, data=afk_data))

