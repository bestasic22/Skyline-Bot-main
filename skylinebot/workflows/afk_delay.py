import discord
import datetime
import asyncio

import storage
from skylinebot.engine.bot_runtime import AutoShardedBot

import storage.afk
from skylinebot.console.logging import logger
import traceback, sys

from skylinebot.style import color


async def afk_delay(bot: AutoShardedBot, data):
    try:
        if not data.get('afk_end'):
            table_name = getattr(
                storage.afk,
                "COLLECTION_NAME",
                getattr(storage.afk, "CollectionName", "afk"),
            )
            return logger.warning(f"Error updating table {table_name}: afk_end is not set")
        afk_end = data.get('afk_end')
        second_delay = (afk_end - datetime.datetime.now(tz=datetime.timezone.utc)).total_seconds()
        
        for i in range(int(second_delay)):
            if second_delay < 0:
                break
            if data.get('guild_id'):
                cache = bot.cache.afk.get('guilds',{}).get(str(data.get('guild_id')),{}).get(str(data.get('user_id')),{})
                if not cache:
                    return logger.warning(f"Afk cache not found for guild afk user {data.get('guild_id')} user {data.get('user_id')}")
            else:
                cache = bot.cache.afk.get('global',{}).get(str(data.get('user_id')),{})
                if not cache:
                    return logger.warning(f"Afk cache not found for global user {data.get('user_id')}")
            if cache.get('id') != data.get('id'):
                return logger.warning(f"ไม่อยู่ Delay stopped for {data.get('id')} as cache id is not same")
            await asyncio.sleep(1)
        
        
        await storage.afk.delete(id=data.get('id'))

        user = await bot.fetch_user(data.get('user_id'))
        if not user:
            return logger.warning(f"ผู้ใช้ not found for id {data.get('user_id')} after delay")

        if data.get('guild_id'):
            await user.send(
                embed=discord.Embed(
                    title="ยกเลิกสถานะ ไม่อยู่ แล้ว",
                    description=f"สถานะ ไม่อยู่ ของคุณใน {bot.get_guild(data.get('guild_id')).name} ถูกยกเลิกแล้ว",
                    color=color.green
                )
            )
        else:
            await user.send(
                embed=discord.Embed(
                    title="ยกเลิกสถานะ ไม่อยู่ แล้ว",
                    description="สถานะ ไม่อยู่ ทั่วระบบของคุณถูกยกเลิกแล้ว",
                    color=color.green
                )
            )
        
    
    except Exception as e:
        logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")


