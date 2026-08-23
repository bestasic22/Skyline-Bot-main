import discord
import asyncio
import datetime
import traceback
import sys
import os

from skylinebot.engine.bot_runtime import AutoShardedBot

from skylinebot.memory.cache import cache
import storage.auto_responder
import storage.guilds
import storage.media_channels
import storage.users
import storage.welcomer_settings
from skylinebot.console.logging import logger
from skylinebot.style import color

from skylinebot.config.config import Types

redeem_code_types = Types.redeem_code_types

import storage
import json

_NICKNAME_SUFFIXES = ("Prime", "Support")


def _safe_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, tuple):
        return list(value)
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _normalize_guild_subscription_code(raw_value: str | None) -> str:
    normalized = str(raw_value or "free").strip().lower()
    mapping = {
        "free": "free",
        "silver": "silver_guild_preminum",
        "silver_guild_preminum": "silver_guild_preminum",
        "silver_guild_premium": "silver_guild_preminum",
        "gold": "golden_guild_premium",
        "gole": "golden_guild_premium",
        "golden": "golden_guild_premium",
        "golden_guild_premium": "golden_guild_premium",
        "gole_guild_premium": "golden_guild_premium",
        "diamond": "diamond_guild_premium",
        "diamond_guild_premium": "diamond_guild_premium",
        "permanent": "permanent_guild_premium",
        "lifetime": "permanent_guild_premium",
        "forever": "permanent_guild_premium",
        "permanent_guild_premium": "permanent_guild_premium",
        "lifetime_guild_premium": "permanent_guild_premium",
    }
    return mapping.get(normalized, normalized or "free")


def _safe_add_days(base: datetime.datetime | None, days: int) -> datetime.datetime:
    base_dt = base or datetime.datetime.now()
    if getattr(base_dt, "tzinfo", None) is not None:
        base_dt = base_dt.astimezone().replace(tzinfo=None)

    max_dt = datetime.datetime.max.replace(microsecond=0)
    min_dt = datetime.datetime.min
    try:
        return base_dt + datetime.timedelta(days=days)
    except OverflowError:
        return max_dt if days >= 0 else min_dt


def _expiry_text(expires_at: datetime.datetime | str | None) -> str:
    if not expires_at:
        return "Lifetime"
    if not isinstance(expires_at, datetime.datetime):
        try:
            raw = str(expires_at).strip()
            if raw:
                parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone().replace(tzinfo=None)
                expires_at = parsed
            else:
                return "Lifetime"
        except Exception:
            return "Lifetime"
    try:
        return f"<t:{int(expires_at.timestamp())}:F>"
    except (OverflowError, ValueError, OSError):
        return "Lifetime"


def _support_guild_id_from_env() -> int | None:
    raw = str(os.getenv("SUPPORT_GUILD_ID", "")).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _strip_suffixes(value: str) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    parts = text.split(" ")
    suffix_tokens = {item.casefold() for item in _NICKNAME_SUFFIXES}
    while parts and parts[-1].casefold() in suffix_tokens:
        parts.pop()
    return " ".join(parts).strip()


def _desired_guild_suffix(*, guild_id: int, subscription_code: str) -> str | None:
    support_guild_id = _support_guild_id_from_env()
    if support_guild_id is not None and int(guild_id) == int(support_guild_id):
        return "Support"
    if str(subscription_code or "").strip().lower() != "free":
        return "Prime"
    return None


async def _sync_guild_bot_nickname(bot: AutoShardedBot, guild_id: int, subscription_code: str) -> None:
    try:
        guild = bot.get_guild(int(guild_id))
        if guild is None or guild.me is None:
            return

        current_display = str(guild.me.display_name or "")
        desired_suffix = _desired_guild_suffix(guild_id=int(guild_id), subscription_code=subscription_code)
        base_name = _strip_suffixes(current_display)
        desired_name = f"{base_name} {desired_suffix}".strip() if desired_suffix else base_name

        if not desired_name:
            return

        current_clean = " ".join(current_display.split()).strip()
        if current_clean == desired_name:
            return

        await guild.me.edit(nick=desired_name)
    except Exception as e:
        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")


async def change_user_subscription(bot:AutoShardedBot,user_id:int,subscription:str=None,valid_for_days:int=None):
    try:
        redeem_code_types = {
            "user_no_prefix": "ผู้ใช้ No พรีฟิกซ์"
        }
        if subscription:
            if subscription.lower() not in redeem_code_types.keys():
                return logger.error(f"Invalid Subscription Type: {subscription} for user_id: {user_id}")
        else:
            subscription = 'free'
            
        user_cache = cache.users.get(str(user_id),{})
        if not user_cache:
            await storage.users.insert(
                user_id=user_id
            )
            user_cache = cache.users.get(str(user_id),{})
        
        if subscription.lower() == 'user_no_prefix':
            if not valid_for_days:
                expires_at = ""
            else:
                no_prefix_end = user_cache.get('no_prefix_end')
                if no_prefix_end:
                    expires_at = _safe_add_days(no_prefix_end, valid_for_days)
                else:
                    expires_at = _safe_add_days(datetime.datetime.now(), valid_for_days)

            try:
                await storage.users.update(
                    id=user_cache.get("id"),
                    user_id=user_id,
                    no_prefix=True,
                    no_prefix_subscription=True,
                    no_prefix_end=expires_at
                )
                logger.info(f"Updated ผู้ใช้ Subscription to ผู้ใช้ No พรีฟิกซ์ for user_id: {user_id}")
                async def send_no_prefix_added_dm():
                    try:
                        user = await bot.fetch_user(user_id)
                        embed = discord.Embed(
                            title="เพิ่มสิทธิ์ใช้งานแบบไม่ต้องมี พรีฟิกซ์ แล้ว",
                            description=f"คุณได้รับสิทธิ์ใช้งานแบบไม่ต้องมี พรีฟิกซ์ ถึงวันที่ {_expiry_text(expires_at)}",
                            color=color.green
                        )
                        await user.send(embed=embed)
                    except Exception as e:
                        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                try:
                    asyncio.create_task(send_no_prefix_added_dm())
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
        elif subscription.lower() == 'free':
            try:
                await storage.users.update(
                    id=user_cache.get("id"),
                    user_id=user_id,
                    no_prefix=False,
                    no_prefix_subscription=False,
                    no_prefix_end=""
                )
                logger.info(f"Updated ผู้ใช้ Subscription to Free for user_id: {user_id}")
                async def send_no_prefix_removed_dm():
                    try:
                        user = await bot.fetch_user(user_id)
                        await user.send(embed=discord.Embed(description="สิทธิ์ใช้งานแบบไม่ต้องมี พรีฟิกซ์ ของคุณถูกยกเลิกแล้ว", color=color.red))
                    except Exception as e:
                        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
                try:
                    asyncio.create_task(send_no_prefix_removed_dm())
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
        else:
            logger.error(f"Invalid Subscription Type: {subscription} for user_id: {user_id}")
    except Exception as e:
        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

async def change_guild_subscription(
    bot: AutoShardedBot,
    guild_id: int,
    subscription: str = None,
    valid_for_days: int = None,
    exact_end: datetime.datetime | None = None,
):
    try:
        subscription = _normalize_guild_subscription_code(subscription)
        if subscription:
            if subscription.lower() not in redeem_code_types.keys() and subscription.lower() not in ['free']:
                return logger.error(f"Invalid Subscription Type: {subscription} for guild_id: {guild_id}")
        else:
            subscription = 'free'
            
        guild_cache = cache.guilds.get(str(guild_id),{})
        if not guild_cache:
            await storage.guilds.insert(
                guild_id=guild_id
            )
            guild_cache = cache.guilds.get(str(guild_id),{})
        welcomer_cache = cache.welcomer_settings.get(str(guild_id),{})
        if not welcomer_cache:
            await storage.welcomer_settings.insert(
                guild_id=guild_id
            )
            welcomer_cache = cache.welcomer_settings.get(str(guild_id),{})

        if exact_end:
            expires_at = exact_end
        elif not valid_for_days:
            expires_at = ""
        else:
            subscription_end = guild_cache.get('subscription_end')
            if subscription_end:
                expires_at = _safe_add_days(subscription_end, valid_for_days)
            else:
                expires_at = _safe_add_days(datetime.datetime.now(), valid_for_days)
        if subscription.lower() == "permanent_guild_premium":
            expires_at = ""

        previous_subscription = str(guild_cache.get("subscription") or "").strip().lower()
        previous_expires_at = str(guild_cache.get("subscription_end") or "").strip()
        next_subscription = str(subscription or "free").strip().lower()
        next_expires_at = str(expires_at or "").strip()
        has_changed = (previous_subscription != next_subscription) or (previous_expires_at != next_expires_at)

        if subscription.lower() == 'silver_guild_preminum':
            try:
                await storage.guilds.update(
                    id=guild_cache.get("id"),
                    guild_id=guild_id,
                    subscription="silver_guild_preminum",
                    subscription_end=expires_at
                )
                logger.info(f"Updated กิลด์ Subscription to Silver กิลด์ Premium for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            try:
                await storage.welcomer_settings.update(
                    id=welcomer_cache.get("id"),
                    guild_id=guild_id,
                    autoroles_limit=5
                )
                logger.info(f"Updated Autoroles Limit to 5 for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            async def send_silver_guild_premium_dm():
                try:
                    guild = bot.get_guild(guild_id)
                    embed = discord.Embed(
                        title="เพิ่มพรีเมียมกิลด์ระดับซิลเวอร์แล้ว",
                        description=f"กิลด์ **{guild.name}** ได้รับพรีเมียมระดับ Silver ถึงวันที่ {_expiry_text(expires_at)}",
                        color=color.green
                    )
                    await guild.owner.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            if has_changed:
                try:
                    asyncio.create_task(send_silver_guild_premium_dm())
                except Exception:
                    pass
            await _sync_guild_bot_nickname(
                bot=bot,
                guild_id=int(guild_id),
                subscription_code="silver_guild_preminum",
            )
        elif subscription.lower() == 'golden_guild_premium':
            try:
                await storage.guilds.update(
                    id=guild_cache.get("id"),
                    guild_id=guild_id,
                    subscription="golden_guild_premium",
                    subscription_end=expires_at
                )
                logger.info(f"Updated กิลด์ Subscription to Gole กิลด์ Premium for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            try:
                await storage.welcomer_settings.update(
                    id=welcomer_cache.get("id"),
                    guild_id=guild_id,
                    autoroles_limit=10
                )
                logger.info(f"Updated Autoroles Limit to 10 for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            async def send_golden_guild_premium_dm():
                try:
                    guild = bot.get_guild(guild_id)
                    embed = discord.Embed(
                        title="เพิ่มพรีเมียมกิลด์ระดับ Gole แล้ว",
                        description=f"กิลด์ **{guild.name}** ได้รับพรีเมียมระดับ Gole ถึงวันที่ {_expiry_text(expires_at)}",
                        color=color.green
                    )
                    await guild.owner.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            if has_changed:
                try:
                    asyncio.create_task(send_golden_guild_premium_dm())
                except Exception:
                    pass
            await _sync_guild_bot_nickname(
                bot=bot,
                guild_id=int(guild_id),
                subscription_code="golden_guild_premium",
            )
        elif subscription.lower() == 'permanent_guild_premium':
            try:
                await storage.guilds.update(
                    id=guild_cache.get("id"),
                    guild_id=guild_id,
                    subscription="permanent_guild_premium",
                    subscription_end=expires_at
                )
                logger.info(f"Updated กิลด์ Subscription to Permanent กิลด์ Premium for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            try:
                await storage.welcomer_settings.update(
                    id=welcomer_cache.get("id"),
                    guild_id=guild_id,
                    autoroles_limit=20
                )
                logger.info(f"Updated Autoroles Limit to 20 for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            async def send_permanent_guild_premium_dm():
                try:
                    guild = bot.get_guild(guild_id)
                    embed = discord.Embed(
                        title="เพิ่มพรีเมียมกิลด์แบบถาวรแล้ว",
                        description=f"กิลด์ **{guild.name}** ได้รับพรีเมียมแบบถาวร (Permanent) เรียบร้อยแล้ว",
                        color=color.green
                    )
                    await guild.owner.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            if has_changed:
                try:
                    asyncio.create_task(send_permanent_guild_premium_dm())
                except Exception:
                    pass
            await _sync_guild_bot_nickname(
                bot=bot,
                guild_id=int(guild_id),
                subscription_code="permanent_guild_premium",
            )
        elif subscription.lower() == 'diamond_guild_premium':
            try:
                await storage.guilds.update(
                    id=guild_cache.get("id"),
                    guild_id=guild_id,
                    subscription="diamond_guild_premium",
                    subscription_end=expires_at
                )
                logger.info(f"Updated กิลด์ Subscription to Diamond กิลด์ Premium for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            try:
                await storage.welcomer_settings.update(
                    id=welcomer_cache.get("id"),
                    guild_id=guild_id,
                    autoroles_limit=15
                )
                logger.info(f"Updated Autoroles Limit to 15 for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            async def send_diamond_guild_premium_dm():
                try:
                    guild = bot.get_guild(guild_id)
                    embed = discord.Embed(
                        title="เพิ่มพรีเมียมกิลด์ระดับไดมอนด์แล้ว",
                        description=f"กิลด์ **{guild.name}** ได้รับพรีเมียมระดับ Diamond ถึงวันที่ {_expiry_text(expires_at)}",
                        color=color.green
                    )
                    await guild.owner.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            if has_changed:
                try:
                    asyncio.create_task(send_diamond_guild_premium_dm())
                except Exception:
                    pass
            await _sync_guild_bot_nickname(
                bot=bot,
                guild_id=int(guild_id),
                subscription_code="diamond_guild_premium",
            )
        elif subscription.lower() == 'free':
            try:
                await storage.guilds.update(
                    id=guild_cache.get("id"),
                    guild_id=guild_id,
                    subscription="free",
                    subscription_end=""
                )
                logger.info(f"Updated กิลด์ Subscription to Free for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            try:
                # update autoroles limit to 3 if subscription is free
                cuted_autoroles = _safe_list(welcomer_cache.get("autoroles"))[:3]
                greet_channels = _safe_list(welcomer_cache.get("greet_channels"))[:5]
                await storage.welcomer_settings.update(
                    id=welcomer_cache.get("id"),
                    guild_id=guild_id,
                    autoroles_limit=3,
                    autoroles=json.dumps(cuted_autoroles),
                    autonick=False,
                    greet_channels=json.dumps(greet_channels)
                )
                logger.info(f"Updated Autoroles Limit to 3 for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

            
            try:
                # delete limited media channels if any for the guild if subscription is free
                await storage.media_channels.delete_limited(limit=1,guild_id=guild_id)
                logger.info(f"Deleted Limited Media Channels for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

            try:
                await storage.auto_responder.delete_limited(limit=5,guild_id=guild_id)
                logger.info(f"Deleted Limited Auto Responders for guild_id: {guild_id}")
            except Exception as e:
                logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

            async def send_free_dm():
                try:
                    guild = bot.get_guild(guild_id)
                    embed = discord.Embed(
                        title="ยกเลิกการสมัครใช้งานแล้ว",
                        description=f"พรีเมียมของกิลด์ **{guild.name}** ถูกยกเลิกแล้ว",
                        color=color.green
                    )
                    await guild.owner.send(embed=embed)
                except Exception as e:
                    logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
            if has_changed:
                try:
                    asyncio.create_task(send_free_dm())
                except Exception:
                    pass
            await _sync_guild_bot_nickname(
                bot=bot,
                guild_id=int(guild_id),
                subscription_code="free",
            )
        else:
            logger.error(f"Invalid Subscription Type: {subscription} for guild_id: {guild_id}")
    except Exception as e:
        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")
