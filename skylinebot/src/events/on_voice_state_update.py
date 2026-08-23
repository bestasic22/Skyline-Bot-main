import datetime,asyncio,discord
import json
import time
from discord.ext import commands
from typing import Any

from skylinebot.console.logging import logger
from skylinebot.src.checks import checks

import traceback,sys

from skylinebot.memory.cache import cache

from storage import j2c as j2c_db
from storage import j2c_settings as j2c_settings_db
import storage

from skylinebot.style import color

from skylinebot.engine.bot_runtime import AutoShardedBot


from skylinebot.src.modules import j2c_controller

from aiohttp import ClientResponseError

from aiohttp import ClientResponseError

TEMP_CHANNELS_CONFIG_KEY_PREFIX = "probot_temp_channels_v1_guild_"

async def retry_operation(operation, *args, retries=5, delay=1, backoff=2, **kwargs):
    for attempt in range(retries):
        try:
            return await operation(*args, **kwargs)
        except ClientResponseError as e:
            if e.status == 429:  # HTTP status code for Too Many Requests
                retry_after = int(e.headers.get('Retry-After', delay))
                await asyncio.sleep(retry_after)
            else:
                raise
        await asyncio.sleep(delay)
        delay *= backoff
    raise Exception("Max retries exceeded")

async def change_j2c_owner(bot,data,channel=None,new_owner=None):

        if not channel:
            channel = bot.get_channel(data.get('channel_id'))
        if not channel:
            return logger.error(f"Channel not found in change_j2c_owner")
        if not isinstance(channel,discord.VoiceChannel):
            return logger.error(f"Channel is not a voice channel in change_j2c_owner")
        if not new_owner:
            # get a random member from the channel
            members = [member for member in channel.members if not member.bot]
            new_owner = members[0]
        if not new_owner:
            return logger.error(f"New owner not found in change_j2c_owner")
        old_owner = bot.get_user(data.get('owner_id'))
        try:
            if old_owner:
                # remove old owner from the channel overwrites
                try:
                    await channel.set_permissions(old_owner,overwrite=None)
                except Exception as e:
                    logger.error(f"Error in on_voice_state_update.change_j2c_owner.remove_old_owner: {e}")
            # add new owner perms_overwrites to the channel
            permissions = discord.PermissionOverwrite(
                view_channel=True,
                manage_channels=True,
                connect=True,
                speak=True,
                mute_members=True,
                deafen_members=True,
                manage_messages=True,
                stream=True,
                send_messages=True,
                add_reactions=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True
            )
            await channel.set_permissions(new_owner,overwrite=permissions)

            await j2c_db.update(id=data.get('id'),owner_id=new_owner.id)

            try:
                await retry_operation(channel.edit, name=f"{new_owner.display_name}'s VC")
            except Exception as e:
                logger.error(f"Error in on_voice_state_update.change_j2c_owner.edit_channel_name: {e}")
        except Exception as e:
            logger.error(f"Error in on_voice_state_update.change_j2c_owner: {e}")



class on_voice_state_update(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot
        self._temp_settings_runtime_cache = {}

    @staticmethod
    def _parse_channel_id(raw_value):
        if raw_value in (None, "", 0):
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    async def _auto_fix_swapped_j2c_settings(self, guild_id: int):
        settings = cache.j2c_settings.get(str(guild_id), {})
        settings_id = settings.get("id")
        if not settings_id:
            return

        create_vc_channel_id = self._parse_channel_id(settings.get("create_vc_channel_id"))
        create_vc_category_id = self._parse_channel_id(settings.get("create_vc_category_id"))
        if not create_vc_channel_id or not create_vc_category_id:
            return

        configured_vc_channel = self.bot.get_channel(create_vc_channel_id)
        configured_category_channel = self.bot.get_channel(create_vc_category_id)

        if not isinstance(configured_vc_channel, discord.CategoryChannel):
            return
        if not isinstance(configured_category_channel, discord.VoiceChannel):
            return

        await j2c_settings_db.update(
            id=settings_id,
            create_vc_channel_id=configured_category_channel.id,
            create_vc_category_id=configured_vc_channel.id,
        )
        logger.info(
            f"Auto-fixed swapped J2C settings in voice event for guild {guild_id}: vc_channel_id={configured_category_channel.id}, vc_category_id={configured_vc_channel.id}"
        )

    @staticmethod
    def _to_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        raw = str(value or "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def _to_int(value, default=0, min_value=None, max_value=None):
        try:
            out = int(value)
        except Exception:
            out = int(default)
        if min_value is not None:
            out = max(min_value, out)
        if max_value is not None:
            out = min(max_value, out)
        return out

    async def _load_temp_runtime_settings(self, guild_id: int) -> dict:
        now = time.time()
        cached = self._temp_settings_runtime_cache.get(str(guild_id), {})
        cached_at = float(cached.get("cached_at") or 0)
        if now - cached_at <= 20 and isinstance(cached.get("data"), dict):
            return cached["data"]

        j2c_row = cache.j2c_settings.get(str(guild_id), {}) or {}
        data = {
            "enabled": bool(j2c_row.get("enabled", False)),
            "create_vc_channel_id": self._parse_channel_id(j2c_row.get("create_vc_channel_id")),
            "create_vc_category_id": self._parse_channel_id(j2c_row.get("create_vc_category_id")),
            "delete_delay_seconds": 3,
            "max_channels_per_user": 1,
            "default_user_limit": 0,
            "enable_role_id": None,
            "disable_role_id": None,
            "enabled_channel_id": None,
            "disabled_channel_id": None,
        }
        try:
            row = await storage.dashboard_config.get(
                config_key=f"{TEMP_CHANNELS_CONFIG_KEY_PREFIX}{guild_id}"
            )
            raw = str((row or {}).get("config_value") or "").strip()
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}

        if isinstance(payload, dict):
            if payload.get("enabled") is not None:
                data["enabled"] = self._to_bool(payload.get("enabled"), data["enabled"])
            raw_create_channel = self._parse_channel_id(payload.get("create_vc_channel_id"))
            raw_create_category = self._parse_channel_id(payload.get("create_vc_category_id"))
            if raw_create_channel:
                data["create_vc_channel_id"] = raw_create_channel
            if raw_create_category:
                data["create_vc_category_id"] = raw_create_category

            data["delete_delay_seconds"] = self._to_int(
                payload.get("delete_delay_seconds", data["delete_delay_seconds"]),
                default=data["delete_delay_seconds"],
                min_value=0,
                max_value=3600,
            )
            data["max_channels_per_user"] = self._to_int(
                payload.get("max_channels_per_user", data["max_channels_per_user"]),
                default=data["max_channels_per_user"],
                min_value=1,
                max_value=25,
            )
            data["default_user_limit"] = self._to_int(
                payload.get("default_user_limit", data["default_user_limit"]),
                default=data["default_user_limit"],
                min_value=0,
                max_value=99,
            )
            data["enable_role_id"] = self._parse_channel_id(payload.get("enable_role_id"))
            data["disable_role_id"] = self._parse_channel_id(payload.get("disable_role_id"))
            data["enabled_channel_id"] = self._parse_channel_id(payload.get("enabled_channel_id"))
            data["disabled_channel_id"] = self._parse_channel_id(payload.get("disabled_channel_id"))

        self._temp_settings_runtime_cache[str(guild_id)] = {
            "cached_at": now,
            "data": data,
        }
        return data
    
    j2c_cooldown_data = {}

    async def voice_state_update_log(self,member:discord.Member,before:discord.VoiceState,after:discord.VoiceState):
        try:
            # only join or leave or move will pass else will return in action
            if before.channel == after.channel:
                return 

            if before.channel and after.channel:
                action = "move"
            elif before.channel and not after.channel:
                action = "leave"
            elif not before.channel and after.channel:
                action = "join"
            else:
                return 

            
            guilds_log_cache = cache.guilds_log.get(str(member.guild.id))
            if not guilds_log_cache:
                return
            if not guilds_log_cache.get('enabled'):
                return logger.debug(f"Voice logging is disabled for guild {member.guild.name}")
            channel_id = guilds_log_cache.get('voice_state_update_channel_id')
            if not channel_id:
                return logger.debug(f"Voice state log channel is not configured for {member.guild.name}")
            
            if action == "move":
                embed = discord.Embed(
                    title=f'{member.display_name} has moved to a different voice channel',
                    description=f'**__User:__** {member.mention}\n**__User ID:__** `{member.id}`\n\n**__From Channel:__** {before.channel.mention}\n**__To Channel:__** {after.channel.mention}\n\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>',
                    color=color.yellow
                )
            elif action == "join":
                embed = discord.Embed(
                    title=f'{member.display_name} has joined a voice channel',
                    description=f'**__User:__** {member.mention}\n**__User ID:__** `{member.id}`\n**__Channel:__** {after.channel.mention}\n\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>',
                    color=color.green
                )
            elif action == "leave":
                embed = discord.Embed(
                    title=f'{member.display_name} has left a voice channel',
                    description=f'**__User:__** {member.mention}\n**__User ID:__** `{member.id}`\n**__Channel:__** {before.channel.mention}\n\n**__Time:__** <t:{int(datetime.datetime.now().timestamp())}>',
                    color=color.red
                )
            embed.set_footer(text=f'User ID: {member.id}')
            embed.set_thumbnail(url=member.display_avatar.url)
            await self.bot.log.send(guild=member.guild,embed=embed,type=f"voice_state_update")
        except Exception as e:
            logger.error(f"Error in on_voice_state_update.voice_state_update_log: {e}")

    

    async def process_existing_vc(self,data):
        try:
            channel = self.bot.get_channel(data.get('channel_id'))
            if not channel:
                return await j2c_db.delete(id=data.get('id'))
            if not isinstance(channel,discord.VoiceChannel):
                return await j2c_db.delete(id=data.get('id'))
            owner_id = data.get('owner_id')
            if owner_id in [member.id for member in channel.members]:
                return logger.debug(f"Owner is still in the channel")
            if len([member for member in channel.members if not member.bot]) == 0:
                temp_settings = await self._load_temp_runtime_settings(channel.guild.id)
                delete_delay = self._to_int(
                    temp_settings.get("delete_delay_seconds", 0),
                    default=0,
                    min_value=0,
                    max_value=3600,
                )
                if delete_delay > 0:
                    await asyncio.sleep(delete_delay)
                    channel = self.bot.get_channel(data.get('channel_id'))
                    if not channel:
                        return await j2c_db.delete(id=data.get('id'))
                    if not isinstance(channel, discord.VoiceChannel):
                        return await j2c_db.delete(id=data.get('id'))
                    if len([member for member in channel.members if not member.bot]) > 0:
                        return logger.debug(f"Skip delete J2C channel {channel.id}: members rejoined")
                await channel.delete()
                await j2c_db.delete(id=data.get('id'))
            else:
                await change_j2c_owner(self.bot,data,channel)               
        except Exception as e:
            logger.error(f"Error in on_voice_state_update.remove_existing_vc: {e}")

    @staticmethod
    def _interaction_custom_id(interaction: discord.Interaction) -> str:
        try:
            payload = interaction.data if isinstance(interaction.data, dict) else {}
            return str(payload.get("custom_id") or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _interaction_member(interaction: discord.Interaction) -> discord.Member | None:
        user = getattr(interaction, "user", None)
        return user if isinstance(user, discord.Member) else None

    def _member_current_j2c(self, member: discord.Member | None) -> tuple[dict[str, Any] | None, discord.VoiceChannel | None]:
        if not member or not getattr(member, "voice", None) or not getattr(member.voice, "channel", None):
            return None, None
        channel = member.voice.channel
        if not isinstance(channel, discord.VoiceChannel):
            return None, None
        row = cache.j2c.get(str(channel.id), {})
        if not isinstance(row, dict) or not row:
            return None, None
        return row, channel

    async def _send_ephemeral_text(
        self,
        interaction: discord.Interaction,
        content: str,
    ) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content=content, ephemeral=True)
            else:
                await interaction.response.send_message(content=content, ephemeral=True)
        except Exception:
            return

    async def _show_tempiface_user_select(
        self,
        interaction: discord.Interaction,
        *,
        title: str,
        placeholder: str,
        callback_handler,
    ) -> None:
        requester = self._interaction_member(interaction)
        if not requester:
            await self._send_ephemeral_text(interaction, "ไม่พบผู้ใช้ที่เรียกคำสั่ง")
            return

        view = discord.ui.View(timeout=60)
        select = discord.ui.UserSelect(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
        )

        async def _callback(select_interaction: discord.Interaction):
            if select_interaction.user.id != requester.id:
                await self._send_ephemeral_text(select_interaction, "เมนูนี้เป็นของผู้ใช้ที่กดปุ่มเท่านั้น")
                return
            selected = select.values[0] if getattr(select, "values", None) else None
            member = selected if isinstance(selected, discord.Member) else None
            if not member and isinstance(selected, discord.User) and select_interaction.guild:
                try:
                    member = await select_interaction.guild.fetch_member(selected.id)
                except Exception:
                    member = None
            if not member:
                await self._send_ephemeral_text(select_interaction, "ไม่พบสมาชิกที่เลือก")
                return
            await callback_handler(select_interaction, member)

        select.callback = _callback
        view.add_item(select)
        await self._send_ephemeral_text(interaction, title)
        try:
            await interaction.edit_original_response(view=view)
        except Exception:
            pass

    async def _handle_tempiface_component(self, interaction: discord.Interaction, action: str) -> None:
        member = self._interaction_member(interaction)
        if not member or not interaction.guild:
            await self._send_ephemeral_text(interaction, "ใช้ได้เฉพาะในเซิร์ฟเวอร์เท่านั้น")
            return

        action = str(action or "").strip().lower()
        room_data, voice_channel = self._member_current_j2c(member)

        async def _require_owner_room() -> tuple[dict[str, Any] | None, discord.VoiceChannel | None]:
            if not room_data or not voice_channel:
                await self._send_ephemeral_text(interaction, "คุณต้องอยู่ในห้อง Join To Create VC ก่อน")
                return None, None
            if int(room_data.get("owner_id") or 0) != member.id:
                await self._send_ephemeral_text(interaction, "คุณไม่ใช่เจ้าของห้องนี้")
                return None, None
            return room_data, voice_channel

        if action == "name":
            owner_row, owner_channel = await _require_owner_room()
            if not owner_row or not owner_channel:
                return

            class RenameModal(discord.ui.Modal, title="เปลี่ยนชื่อห้อง"):
                new_name = discord.ui.TextInput(
                    label="ชื่อห้องใหม่",
                    placeholder="เช่น ห้องของฉัน",
                    min_length=2,
                    max_length=100,
                    required=True,
                    style=discord.TextStyle.short,
                    default=owner_channel.name[:100],
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    modal_member = self._outer._interaction_member(modal_interaction)
                    if not modal_member:
                        await self._outer._send_ephemeral_text(modal_interaction, "ไม่พบข้อมูลผู้ใช้")
                        return
                    row, channel = self._outer._member_current_j2c(modal_member)
                    if not row or not channel or int(row.get("owner_id") or 0) != modal_member.id:
                        await self._outer._send_ephemeral_text(modal_interaction, "คุณไม่ได้เป็นเจ้าของห้อง J2C ที่กำลังใช้งาน")
                        return
                    try:
                        await channel.edit(name=str(self.new_name.value or "").strip()[:100])
                        await self._outer._send_ephemeral_text(modal_interaction, f"เปลี่ยนชื่อห้องเป็น `{channel.name}` แล้ว")
                    except Exception as error:
                        await self._outer._send_ephemeral_text(modal_interaction, f"เปลี่ยนชื่อห้องไม่สำเร็จ: {error}")

            modal = RenameModal()
            modal._outer = self
            await interaction.response.send_modal(modal)
            return

        if action == "limit":
            owner_row, owner_channel = await _require_owner_room()
            if not owner_row or not owner_channel:
                return

            class LimitModal(discord.ui.Modal, title="จำกัดจำนวนสมาชิก"):
                user_limit = discord.ui.TextInput(
                    label="จำนวนสมาชิก (0 = ไม่จำกัด)",
                    placeholder="0-99",
                    min_length=1,
                    max_length=2,
                    required=True,
                    style=discord.TextStyle.short,
                    default=str(owner_channel.user_limit or 0),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    modal_member = self._outer._interaction_member(modal_interaction)
                    if not modal_member:
                        await self._outer._send_ephemeral_text(modal_interaction, "ไม่พบข้อมูลผู้ใช้")
                        return
                    row, channel = self._outer._member_current_j2c(modal_member)
                    if not row or not channel or int(row.get("owner_id") or 0) != modal_member.id:
                        await self._outer._send_ephemeral_text(modal_interaction, "คุณไม่ได้เป็นเจ้าของห้อง J2C ที่กำลังใช้งาน")
                        return
                    try:
                        limit = int(str(self.user_limit.value or "0").strip())
                    except Exception:
                        await self._outer._send_ephemeral_text(modal_interaction, "จำนวนสมาชิกต้องเป็นตัวเลข 0-99")
                        return
                    if limit < 0 or limit > 99:
                        await self._outer._send_ephemeral_text(modal_interaction, "จำนวนสมาชิกต้องอยู่ระหว่าง 0 ถึง 99")
                        return
                    try:
                        await channel.edit(user_limit=(None if limit == 0 else limit))
                        await self._outer._send_ephemeral_text(
                            modal_interaction,
                            f"อัปเดตจำนวนสมาชิกสูงสุดเป็น `{('ไม่จำกัด' if limit == 0 else limit)}` แล้ว",
                        )
                    except Exception as error:
                        await self._outer._send_ephemeral_text(modal_interaction, f"อัปเดตจำนวนสมาชิกไม่สำเร็จ: {error}")

            modal = LimitModal()
            modal._outer = self
            await interaction.response.send_modal(modal)
            return

        if action == "privacy":
            owner_row, owner_channel = await _require_owner_room()
            if not owner_row or not owner_channel:
                return
            try:
                default_role = owner_channel.guild.default_role
                is_locked = bool(owner_channel.permissions_for(default_role).connect) is False
                await owner_channel.set_permissions(default_role, connect=(True if is_locked else False))
                await self._send_ephemeral_text(interaction, "ปลดล็อกห้องแล้ว" if is_locked else "ล็อกห้องแล้ว")
            except Exception as error:
                await self._send_ephemeral_text(interaction, f"เปลี่ยนสถานะล็อกห้องไม่สำเร็จ: {error}")
            return

        if action == "chat":
            owner_row, owner_channel = await _require_owner_room()
            if not owner_row or not owner_channel:
                return
            try:
                default_role = owner_channel.guild.default_role
                overwrite = owner_channel.overwrites_for(default_role)
                is_hidden = overwrite.view_channel is False
                await owner_channel.set_permissions(default_role, view_channel=(True if is_hidden else False))
                await self._send_ephemeral_text(interaction, "แสดงห้องแล้ว" if is_hidden else "ซ่อนห้องแล้ว")
            except Exception as error:
                await self._send_ephemeral_text(interaction, f"เปลี่ยนการมองเห็นห้องไม่สำเร็จ: {error}")
            return

        if action == "region":
            owner_row, owner_channel = await _require_owner_room()
            if not owner_row or not owner_channel:
                return
            view = discord.ui.View(timeout=60)
            options = [
                discord.SelectOption(label="Automatic", value="auto", default=owner_channel.rtc_region is None),
                discord.SelectOption(label="Singapore", value="singapore", default=str(owner_channel.rtc_region or "") == "singapore"),
                discord.SelectOption(label="Hong Kong", value="hong-kong", default=str(owner_channel.rtc_region or "") == "hong-kong"),
                discord.SelectOption(label="Japan", value="japan", default=str(owner_channel.rtc_region or "") == "japan"),
                discord.SelectOption(label="India", value="india", default=str(owner_channel.rtc_region or "") == "india"),
                discord.SelectOption(label="US East", value="us-east", default=str(owner_channel.rtc_region or "") == "us-east"),
                discord.SelectOption(label="US West", value="us-west", default=str(owner_channel.rtc_region or "") == "us-west"),
                discord.SelectOption(label="Europe", value="europe", default=str(owner_channel.rtc_region or "") == "europe"),
            ]
            region_select = discord.ui.Select(placeholder="เลือก Region ห้องเสียง", min_values=1, max_values=1, options=options)

            async def _region_callback(region_interaction: discord.Interaction):
                if region_interaction.user.id != member.id:
                    await self._send_ephemeral_text(region_interaction, "เมนูนี้เป็นของผู้ใช้ที่กดปุ่มเท่านั้น")
                    return
                row, channel = self._member_current_j2c(member)
                if not row or not channel or int(row.get("owner_id") or 0) != member.id:
                    await self._send_ephemeral_text(region_interaction, "คุณไม่ได้เป็นเจ้าของห้อง J2C ที่กำลังใช้งาน")
                    return
                selected = str(region_select.values[0] if region_select.values else "auto").strip().lower()
                next_region = None if selected == "auto" else selected
                try:
                    await channel.edit(rtc_region=next_region)
                    await self._send_ephemeral_text(region_interaction, f"ตั้งค่า Region เป็น `{('Automatic' if next_region is None else next_region)}` แล้ว")
                except Exception as error:
                    await self._send_ephemeral_text(region_interaction, f"ตั้งค่า Region ไม่สำเร็จ: {error}")

            region_select.callback = _region_callback
            view.add_item(region_select)
            await self._send_ephemeral_text(interaction, "เลือกระบบ Region ที่ต้องการสำหรับห้องของคุณ")
            try:
                await interaction.edit_original_response(view=view)
            except Exception:
                pass
            return

        if action in {"trust", "untrust", "block", "unblock", "kick", "transfer"}:
            owner_row, owner_channel = await _require_owner_room()
            if not owner_row or not owner_channel:
                return

            async def _selected_action(select_interaction: discord.Interaction, target_member: discord.Member):
                row, channel = self._member_current_j2c(member)
                if not row or not channel or int(row.get("owner_id") or 0) != member.id:
                    await self._send_ephemeral_text(select_interaction, "คุณไม่ได้เป็นเจ้าของห้อง J2C ที่กำลังใช้งาน")
                    return
                if target_member.bot:
                    await self._send_ephemeral_text(select_interaction, "ไม่สามารถเลือกบอทได้")
                    return
                if target_member.id == member.id and action in {"kick", "block", "untrust", "transfer"}:
                    await self._send_ephemeral_text(select_interaction, "ไม่สามารถทำรายการนี้กับตัวเองได้")
                    return

                try:
                    if action == "trust":
                        await channel.set_permissions(target_member, connect=True, view_channel=True)
                        await self._send_ephemeral_text(select_interaction, f"อนุญาต {target_member.mention} เข้าห้องแล้ว")
                    elif action == "untrust":
                        await channel.set_permissions(target_member, connect=False)
                        await self._send_ephemeral_text(select_interaction, f"ยกเลิกสิทธิ์เข้าห้องของ {target_member.mention} แล้ว")
                    elif action == "block":
                        await channel.set_permissions(target_member, connect=False, view_channel=False)
                        await self._send_ephemeral_text(select_interaction, f"บล็อก {target_member.mention} แล้ว")
                    elif action == "unblock":
                        await channel.set_permissions(target_member, overwrite=None)
                        await self._send_ephemeral_text(select_interaction, f"ปลดบล็อก {target_member.mention} แล้ว")
                    elif action == "kick":
                        if not target_member.voice or target_member.voice.channel != channel:
                            await self._send_ephemeral_text(select_interaction, f"{target_member.mention} ไม่ได้อยู่ในห้องนี้")
                            return
                        await target_member.move_to(None)
                        await self._send_ephemeral_text(select_interaction, f"เตะ {target_member.mention} ออกจากห้องแล้ว")
                    elif action == "transfer":
                        if not target_member.voice or target_member.voice.channel != channel:
                            await self._send_ephemeral_text(select_interaction, f"{target_member.mention} ต้องอยู่ในห้องก่อนจึงจะโอนเจ้าของได้")
                            return
                        await change_j2c_owner(self.bot, row, channel, target_member)
                        await self._send_ephemeral_text(select_interaction, f"โอนเจ้าของห้องให้ {target_member.mention} แล้ว")
                except Exception as error:
                    await self._send_ephemeral_text(select_interaction, f"ทำรายการไม่สำเร็จ: {error}")

            title_map = {
                "trust": "เลือกสมาชิกที่จะอนุญาตเข้าห้อง",
                "untrust": "เลือกสมาชิกที่จะยกเลิกสิทธิ์เข้าห้อง",
                "block": "เลือกสมาชิกที่จะบล็อก",
                "unblock": "เลือกสมาชิกที่จะปลดบล็อก",
                "kick": "เลือกสมาชิกที่จะเตะออกจากห้อง",
                "transfer": "เลือกสมาชิกที่จะรับสิทธิ์เจ้าของห้อง",
            }
            await self._show_tempiface_user_select(
                interaction,
                title=title_map.get(action, "เลือกสมาชิก"),
                placeholder="เลือกสมาชิก",
                callback_handler=_selected_action,
            )
            return

        if action == "claim":
            if not room_data or not voice_channel:
                await self._send_ephemeral_text(interaction, "คุณต้องเข้าห้อง Join To Create VC ก่อนจึงจะ Claim ได้")
                return
            current_owner_id = int(room_data.get("owner_id") or 0)
            if current_owner_id == member.id:
                await self._send_ephemeral_text(interaction, "คุณเป็นเจ้าของห้องนี้อยู่แล้ว")
                return
            owner_still_here = any((not user.bot and user.id == current_owner_id) for user in voice_channel.members)
            if owner_still_here:
                await self._send_ephemeral_text(interaction, "ยัง Claim ไม่ได้เพราะเจ้าของเดิมยังอยู่ในห้อง")
                return
            try:
                await change_j2c_owner(self.bot, room_data, voice_channel, member)
                await self._send_ephemeral_text(interaction, "Claim ห้องสำเร็จแล้ว ตอนนี้คุณเป็นเจ้าของห้อง")
            except Exception as error:
                await self._send_ephemeral_text(interaction, f"Claim ห้องไม่สำเร็จ: {error}")
            return

        if action == "delete":
            owner_row, owner_channel = await _require_owner_room()
            if not owner_row or not owner_channel:
                return
            try:
                channel_id = owner_channel.id
                await owner_channel.delete(reason=f"Deleted by J2C panel ({member.id})")
                await j2c_db.delete(id=owner_row.get("id"))
                await self._send_ephemeral_text(interaction, f"ลบห้อง J2C (`{channel_id}`) แล้ว")
            except Exception as error:
                await self._send_ephemeral_text(interaction, f"ลบห้องไม่สำเร็จ: {error}")
            return

        await self._send_ephemeral_text(interaction, "ไม่รู้จักคำสั่งปุ่มนี้")

    async def j2c_module(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        try:
            await self._auto_fix_swapped_j2c_settings(member.guild.id)
            runtime_settings = await self._load_temp_runtime_settings(member.guild.id)

            if not runtime_settings.get('enabled', False):
                return logger.debug(f"J2C is disabled in {member.guild.name}")
        
            # only join or leave or move will pass else will return in action
            if before.channel == after.channel:
                return 

            if before.channel and after.channel:
                action = "move"
            elif before.channel and not after.channel:
                action = "leave"
            elif not before.channel and after.channel:
                action = "join"
            else:
                return 


            
            if action == "join" or action == "move":
                j2c_snapshot = tuple(list(cache.j2c.items()))
                for channel_id,data in j2c_snapshot:
                    if data.get('owner_id') == member.id:
                        await self.process_existing_vc(data)
                
                if member.id == cache.j2c.get(str(after.channel.id),{}).get('owner_id'):
                    return
                
                configured_create_channel_id = self._parse_channel_id(runtime_settings.get('create_vc_channel_id'))

                if after.channel.id != configured_create_channel_id:
                    return

                enable_role_id = runtime_settings.get("enable_role_id")
                if enable_role_id and enable_role_id not in [role.id for role in member.roles]:
                    await member.move_to(None)
                    return logger.debug(f"J2C blocked: member {member.id} missing enabled role {enable_role_id}")

                disable_role_id = runtime_settings.get("disable_role_id")
                if disable_role_id and disable_role_id in [role.id for role in member.roles]:
                    await member.move_to(None)
                    return logger.debug(f"J2C blocked: member {member.id} has disabled role {disable_role_id}")

                enabled_channel_id = runtime_settings.get("enabled_channel_id")
                if enabled_channel_id:
                    enabled_channel_obj = member.guild.get_channel(enabled_channel_id)
                    if isinstance(enabled_channel_obj, discord.VoiceChannel) and after.channel.id != enabled_channel_id:
                        return logger.debug(f"J2C blocked: joined voice {after.channel.id} but enabled is {enabled_channel_id}")

                disabled_channel_id = runtime_settings.get("disabled_channel_id")
                if disabled_channel_id and after.channel.id == disabled_channel_id:
                    await member.move_to(None)
                    return logger.debug(f"J2C blocked: channel {disabled_channel_id} is disabled")

                max_channels_per_user = self._to_int(
                    runtime_settings.get("max_channels_per_user", 1),
                    default=1,
                    min_value=1,
                    max_value=25,
                )
                active_owned_channels = []
                for _channel_id, row in j2c_snapshot:
                    if int(row.get("guild_id") or 0) != member.guild.id:
                        continue
                    if int(row.get("owner_id") or 0) != member.id:
                        continue
                    owned_channel = self.bot.get_channel(int(row.get("channel_id") or 0))
                    if owned_channel and isinstance(owned_channel, discord.VoiceChannel):
                        active_owned_channels.append(owned_channel.id)
                if len(active_owned_channels) >= max_channels_per_user:
                    await member.move_to(None)
                    try:
                        await member.send(
                            embed=discord.Embed(
                                title="สร้างห้องชั่วคราวไม่สำเร็จ",
                                description=f"คุณสร้างห้องได้พร้อมกันสูงสุด `{max_channels_per_user}` ห้อง",
                                color=color.red,
                            )
                        )
                    except Exception:
                        pass
                    return logger.debug(f"J2C blocked by max_channels_per_user for member {member.id} in guild {member.guild.id}")
                
                # if the member create 3 channel under 5 minutes then return
                if str(member.guild.id) in self.j2c_cooldown_data:
                    if str(member.id) in self.j2c_cooldown_data[str(member.guild.id)]:
                        if self.j2c_cooldown_data[str(member.guild.id)][str(member.id)].get('created',0) >= 3:
                            if datetime.datetime.now().timestamp() - self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['last_created'] < 300:
                                # remove the member from the channel
                                await member.move_to(None)
                                embed = discord.Embed(
                                    title="You have created 3 channels under 5 minutes",
                                    description=f"You can only create 3 channels under 5 minutes. You can try again <t:{int(self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['last_created']+300)}:R>",
                                    color=color.red
                                )
                                try:
                                    await member.send(embed=embed)
                                except Exception as e:
                                    pass               
                                return logger.debug(f"J2C cooldown hit for user {member.id} in guild {member.guild.id}")
                            


                
                configured_category_id = self._parse_channel_id(runtime_settings.get('create_vc_category_id'))
                category = self.bot.get_channel(configured_category_id)

                overwrites = {
                    member: discord.PermissionOverwrite(
                        view_channel=True,
                        manage_channels=True,
                        connect=True,
                        speak=True,
                        mute_members=True,
                        deafen_members=True,
                        manage_messages=True,
                        stream=True,
                        send_messages=True,
                        add_reactions=True,
                        embed_links=True,
                        attach_files=True,
                        read_message_history=True
                    )
                }

                channel = await member.guild.create_voice_channel(
                    name=f"{member.display_name}'s VC",
                    category=category,
                    reason=f"J2C Channel for {member.display_name}",
                    overwrites=overwrites,
                    rtc_region=after.channel.rtc_region,
                    user_limit=(
                        self._to_int(runtime_settings.get("default_user_limit", 0), default=0, min_value=0, max_value=99)
                        if self._to_int(runtime_settings.get("default_user_limit", 0), default=0, min_value=0, max_value=99) > 0
                        else None
                    ),
                )
                if str(member.guild.id) not in self.j2c_cooldown_data:
                    self.j2c_cooldown_data[str(member.guild.id)] = {}
                if str(member.id) not in self.j2c_cooldown_data[str(member.guild.id)]:
                    self.j2c_cooldown_data[str(member.guild.id)][str(member.id)] = {}
                if 'created' not in self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]:
                    self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['created'] = 0
                if 'last_created' not in self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]:
                    self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['last_created'] = 0
                if datetime.datetime.now().timestamp() - self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['last_created'] > 300:
                    self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['created'] = 0
                else:
                    self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['created'] += 1
                self.j2c_cooldown_data[str(member.guild.id)][str(member.id)]['last_created'] = datetime.datetime.now().timestamp()
                data = await j2c_db.insert(
                    channel_id=channel.id,
                    guild_id=member.guild.id,
                    owner_id=member.id
                )
                # move the member to the channel
                await member.move_to(channel)                
                await j2c_controller.controller_module(bot=self.bot,data=data,channel=channel)

            elif action == "leave":
                j2c_snapshot = tuple(list(cache.j2c.items()))
                for channel_id,data in j2c_snapshot:
                    if data.get('owner_id') == member.id:
                        await self.process_existing_vc(data)

        except Exception as e:
            logger.error(f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}")

    # function check if the bot is disconnected from a discord server voice channel
    async def check_bot_disconnected_from_music_player(self,member:discord.Member,before:discord.VoiceState,after:discord.VoiceState):
        try:
            if member != self.bot.user:
                return 
            if not before.channel:
                return 
            if before.channel and after.channel:
                return
            if before.channel and not after.channel:
                # logger.info(f"Bot left a voice channel")
                MusicCog = self.bot.get_cog("Music")
                if MusicCog:
                    await MusicCog.send_music_controls(guild=member.guild, end=True)
            else:
                return
        except Exception as e:
            logger.error(f"Error in on_voice_state_update.check_bot_disconnected_from_music_player: {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            if getattr(interaction, "type", None) != discord.InteractionType.component:
                return
            custom_id = self._interaction_custom_id(interaction)
            if not custom_id.startswith("tempiface:"):
                return
            action = custom_id.split(":", 1)[1].strip().lower()
            allowed_actions = {
                "name",
                "limit",
                "privacy",
                "chat",
                "trust",
                "untrust",
                "kick",
                "region",
                "block",
                "unblock",
                "claim",
                "transfer",
                "delete",
            }
            if action not in allowed_actions:
                await self._send_ephemeral_text(interaction, "ไม่รู้จักคำสั่งปุ่มนี้")
                return
            await self._handle_tempiface_component(interaction, action)
        except Exception as error:
            logger.error(f"Error in on_voice_state_update.on_interaction: {error}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        try:
            asyncio.create_task(self.voice_state_update_log(member,before,after))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.j2c_module(member,before,after))
        except Exception as e:
            pass
        try:
            asyncio.create_task(self.check_bot_disconnected_from_music_player(member,before,after))
        except Exception as e:
            pass
        


