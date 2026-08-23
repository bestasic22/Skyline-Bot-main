from discord.ext import commands
import discord
from skylinebot.style import color
import traceback
import json

from skylinebot.memory.cache import cache

from skylinebot.config import config

def check_ignore_predicate(ctx):
    try:
        guild = getattr(ctx, "guild", None)
        author = getattr(ctx, "author", None)
        channel = getattr(ctx, "channel", None)
        if guild is None or author is None or channel is None:
            return True
        guild_id = str(getattr(guild, "id", ""))
        if not guild_id:
            return True
        if str(author.id) in cache.ignore_data.get('users',{}).get(guild_id,{}):
            return False
        if str(channel.id) in cache.ignore_data.get('channels',{}).get(guild_id,{}):
            return False
        return True
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False

def ignore_check():
    return commands.check(check_ignore_predicate)


def check_blacklist_predicate(ctx):
    try:
        author = getattr(ctx, "author", None)
        guild = getattr(ctx, "guild", None)
        if author is None:
            return True
        if str(author.id) in cache.ban_data.get('users',{}):
            return False
        guild_id = str(getattr(guild, "id", "")) if guild is not None else ""
        if guild_id and guild_id in cache.ban_data.get('guilds',{}):
            return False
        return True
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False

def blacklist_check():
    return commands.check(check_blacklist_predicate)





def check_is_admin_predicate(user):
    if user.id in cache.admins or user.id in cache.owners or user.id in config.users.root:
        return True
    return False

def is_admin():
    return commands.check(check_is_admin_predicate)

def check_is_owner_predicate(ctx):
    if ctx.author.id in cache.owners or ctx.author.id in config.users.root:
        return True
    return False

def is_owner():
    return commands.check(check_is_owner_predicate)

async def check_is_moderator_permissions(ctx:commands.Context,permission:str,role_position_check=False,notify=True):
    try:
        if check_is_admin_predicate(ctx.author):
            return True
        if await check_is_owner_raw(ctx.author,ctx.guild):
            return True
        if role_position_check:
            if ctx.author.top_role.position < ctx.guild.me.top_role.position:
                await ctx.send(embed=discord.Embed(description="คุณใช้คำสั่งนี้ไม่ได้ เพราะบทบาทของคุณต่ำกว่าบอท",color=color.red),delete_after=5)
                return False
        
        if ctx.author.guild_permissions.administrator:
            return True
        
        if hasattr(ctx.author.guild_permissions,permission):
            if getattr(ctx.author.guild_permissions,permission):
                return True
        
        if notify:
            await ctx.send(embed=discord.Embed(description="คุณไม่มีสิทธิ์ที่จำเป็นในการใช้คำสั่งนี้",color=color.red),delete_after=5)
        return False
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False


async def check_for_giveaway_permissions(ctx:commands.Context,permission:str="manage_guild"):
    try:
        if await check_is_owner(ctx,notify=False):
            return True
        if await check_is_moderator_permissions(ctx,permission,notify=False):
            return True
        cache_giveaways_permissions = cache.giveaways_permissions.get(str(ctx.guild.id),{})
        required_role_id = cache_giveaways_permissions.get('required_role_id',None)
        if required_role_id:
            if any([role.id == required_role_id for role in ctx.author.roles if not role.is_default()]):
                return True
        await ctx.send(embed=discord.Embed(description="คุณไม่มีสิทธิ์ที่จำเป็นในการใช้คำสั่งนี้",color=color.red),delete_after=5)
        return False   
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False

async def check_extra_owners(member:discord.Member,guild:discord.Guild):
    try:
        extra_owner_ids = json.loads(cache.guilds.get(str(guild.id),{}).get('extra_owner_ids','[]'))
        guilds_cache = cache.guilds.get(str(guild.id),{})
        guilds_subscription = guilds_cache.get('subscription','free')
        if guilds_subscription == 'free':
            extra_owner_limit = 1
        elif guilds_subscription == 'silver_guild_preminum':
            extra_owner_limit = 5
        elif guilds_subscription == 'golden_guild_premium':
            extra_owner_limit = 10
        elif guilds_subscription in {'diamond_guild_premium', 'permanent_guild_premium', 'lifetime_guild_premium'}:
            extra_owner_limit = 20
        else:
            extra_owner_limit = 1
        if len(extra_owner_ids) > extra_owner_limit:
            return False
        if str(member.id) in extra_owner_ids and member.guild_permissions.administrator:
            return True
        return False
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False

async def check_is_owner_raw(user:discord.User,guild:discord.Guild):
    try:
        extra_owner = await check_extra_owners(user,guild)
        if user==guild.owner or extra_owner:
            return True
        return False
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False




async def close_ticket_permissions(user,guild:discord.Guild,creator_id:int,support_role_ids,notify=True):
    try:
        if check_is_admin_predicate(user):
            return True
        if await check_is_owner_raw(user,guild):
            return True
        if user.id == creator_id:
            return True
        if any([role.id in support_role_ids for role in user.roles]):
            return True
        if notify:
            await user.send(embed=discord.Embed(description="คุณไม่มีสิทธิ์ที่จำเป็นในการปิดตั๋วนี้",color=color.red))
        return False
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False


async def check_is_owner(ctx,notify=True):
    try:
        if ctx.author==ctx.guild.owner or check_is_owner_predicate(ctx) or await check_is_owner_raw(ctx.author,ctx.guild):
            return True
        if notify:
            await ctx.send(embed=discord.Embed(description="คุณไม่ได้รับอนุญาตให้ใช้คำสั่งนี้",color=color.red),delete_after=10)
        return False
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False

async def check_if_user_can_manage_this_role(ctx:commands.Context,role:discord.Role):
    if ctx.guild.me.top_role.position <= role.position:
        await ctx.send(embed=discord.Embed(description="บอทไม่สามารถจัดการบทบาทนี้ได้ เพราะบทบาทนี้สูงกว่าหรือเท่ากับบอท",color=color.red),delete_after=5)
        return False
    if ctx.author == ctx.guild.owner:
        return True
    if ctx.author == role.guild.owner:
        return True
    if ctx.author.top_role.position > role.position:
        return True
    await ctx.send(embed=discord.Embed(description="คุณไม่สามารถจัดการบทบาทนี้ได้ เพราะตำแหน่งบทบาทของคุณไม่สูงพอ",color=color.red),delete_after=5)
    return False

async def check_if_user_can_manage_this_member(ctx:commands.Context,member:discord.Member):
    if ctx.guild.me.top_role.position <= member.top_role.position:
        await ctx.send(embed=discord.Embed(description="บอทไม่สามารถจัดการสมาชิกนี้ได้ เพราะบทบาทของสมาชิกสูงกว่าหรือเท่ากับบอท",color=color.red),delete_after=5)
        return False
    if ctx.author == ctx.guild.owner:
        return True
    if ctx.guild.owner == member:
        await ctx.send(embed=discord.Embed(description="คุณไม่สามารถจัดการเจ้าของเซิร์ฟเวอร์ได้",color=color.red),delete_after=5)
        return False
    if ctx.author == member:
        return True
    if ctx.author.top_role.position > member.top_role.position:
        return True
    await ctx.send(embed=discord.Embed(description="คุณไม่สามารถจัดการสมาชิกนี้ได้ เพราะบทบาทของคุณไม่สูงพอ",color=color.red),delete_after=5)
    return False


async def check_if_user_can_be_banned_or_kicked(ctx:commands.Context,user:discord.Member):
    try:
        guild = ctx.guild
        if guild is None:
            return False

        actor = ctx.author if isinstance(ctx.author, discord.Member) else None
        if actor is None:
            actor = guild.get_member(getattr(ctx.author, "id", 0))
            if actor is None:
                try:
                    actor = await guild.fetch_member(getattr(ctx.author, "id", 0))
                except Exception:
                    actor = None
        if actor is None:
            await ctx.send(embed=discord.Embed(description="ไม่สามารถตรวจสอบข้อมูลผู้สั่งงานได้",color=color.red),delete_after=20)
            return False

        target = user if isinstance(user, discord.Member) else guild.get_member(getattr(user, "id", 0))
        if target is None:
            try:
                target = await guild.fetch_member(getattr(user, "id", 0))
            except Exception:
                target = None
        if target is None:
            await ctx.send(embed=discord.Embed(description="ไม่พบสมาชิกเป้าหมายในเซิร์ฟเวอร์",color=color.red),delete_after=20)
            return False

        bot_user_id = getattr(getattr(ctx, "bot", None), "user", None)
        bot_user_id = getattr(bot_user_id, "id", 0) if bot_user_id else 0
        bot_member = guild.me or guild.get_member(bot_user_id)
        if bot_member is None and bot_user_id:
            try:
                bot_member = await guild.fetch_member(bot_user_id)
            except Exception:
                bot_member = None
        if bot_member is None:
            await ctx.send(embed=discord.Embed(description="ไม่พบข้อมูลบทบาทของบอทในกิลด์นี้",color=color.red),delete_after=20)
            return False

        if actor == target:
            await ctx.send(embed=discord.Embed(description="ล้อกันหรือเปล่า คุณแบนตัวเองไม่ได้",color=color.red),delete_after=20)
            return False
        if target == bot_member:
            await ctx.send(embed=discord.Embed(description="What did I ever do to you?",color=color.red),delete_after=20)
            return False
        # if check_is_admin_predicate(user):
        #     await ctx.send(embed=discord.Embed(description="The User can't be Banned. Because the User is an Bot Admin/Owner",color=color.red),delete_after=20)
        #     return False
        if guild.owner == target:
            await ctx.send(embed=discord.Embed(description="คุณไม่สามารถแบนหรือเตะเจ้าของเซิร์ฟเวอร์ได้",color=color.red),delete_after=20)
            return False
        if actor.top_role.position <= target.top_role.position and guild.owner != actor:
            await ctx.send(embed=discord.Embed(description="คุณไม่สามารถแบนหรือเตะสมาชิกที่มียศสูงกว่าหรือเท่ากับคุณได้",color=color.red),delete_after=20)
            return False
        if bot_member.top_role.position <= target.top_role.position:
            bot_role = f"{bot_member.top_role.name} ({bot_member.top_role.position})"
            target_role = f"{target.top_role.name} ({target.top_role.position})"
            await ctx.send(
                embed=discord.Embed(
                    description=(
                        "บอทไม่สามารถแบนหรือเตะสมาชิกนี้ได้ เพราะยศบอทต้องสูงกว่าเป้าหมาย\n"
                        f"ยศบอท: `{bot_role}` | ยศเป้าหมาย: `{target_role}`"
                    ),
                    color=color.red,
                ),
                delete_after=20,
            )
            return False
        return True
    except Exception as e:
        print(f"Error in file {__file__}: {traceback.format_exc()}")
        return False


