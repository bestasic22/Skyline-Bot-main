import discord


import asyncio


from skylinebot.engine.bot_runtime import AutoShardedBot


from skylinebot.console.logging import logger


from storage import j2c as j2c_db


from skylinebot.style import color


from skylinebot.memory.cache import cache


from skylinebot.src.events import on_voice_state_update
from skylinebot.src.services import VoicePanelPresenter


import traceback, sys


async def controller_module(bot: AutoShardedBot, data, channel=None):

    if not channel:

        channel = await bot.fetch_channel(data.get("channel_id"))

    if not channel:

        return logger.error(f"Channel not found in controller_module")

    if not isinstance(channel, discord.VoiceChannel):

        return logger.error(f"Channel is not a voice channel in controller_module")

    try:

        panel_presenter = VoicePanelPresenter(bot)
        embed = await panel_presenter.build_embed(channel)

        async def get_view():

            view = discord.ui.View(timeout=None)

            name_changer_button = discord.ui.Button(
                label="เปลี่ยนชื่อห้อง",
                style=discord.ButtonStyle.primary,
                emoji="๏ฟฝ",
                row=1,
            )

            name_changer_button.callback = lambda i: name_changer_button_callback(i)

            change_bitrate_button = discord.ui.Button(
                label="เปลี่ยนบิตเรต",
                style=discord.ButtonStyle.primary,
                emoji="",
                row=1,
            )

            change_bitrate_button.callback = lambda i: change_bitrate_button_callback(i)

            change_user_limit_button = discord.ui.Button(
                label="User Limit", style=discord.ButtonStyle.primary, emoji="", row=2
            )

            change_user_limit_button.callback = (
                lambda i: change_user_limit_button_callback(i)
            )

            transfer_ownership_button = discord.ui.Button(
                label="โอนสิทธิ์เจ้าของห้อง",
                style=discord.ButtonStyle.primary,
                emoji="",
                row=2,
            )

            transfer_ownership_button.callback = (
                lambda i: transfer_ownership_button_callback(i)
            )

            switch_region_select = discord.ui.Select(
                placeholder="เลือกภูมิภาคห้อง",
                min_values=1,
                max_values=1,
                options=panel_presenter.build_region_options(channel),
                row=3,
            )

            switch_region_select.callback = lambda i: switch_region_select_callback(i)

            lock_or_unlock_button = discord.ui.Button(
                label=(
                    "ปลดล็อกห้อง"
                    if str(channel.permissions_for(channel.guild.default_role).connect)
                    == "False"
                    else "ล็อกห้อง"
                ),
                style=(
                    discord.ButtonStyle.green
                    if str(channel.permissions_for(channel.guild.default_role).connect)
                    == "False"
                    else discord.ButtonStyle.red
                ),
                emoji=(
                    ""
                    if str(channel.permissions_for(channel.guild.default_role).connect)
                    == "False"
                    else ""
                ),
                row=4,
            )

            lock_or_unlock_button.callback = lambda i: lock_or_unlock_button_callback(i)

            hide_or_unhide_button = discord.ui.Button(
                label=(
                    "เลิกซ่อนห้อง"
                    if str(
                        channel.overwrites_for(channel.guild.default_role).view_channel
                    )
                    == "False"
                    else "ซ่อนห้อง"
                ),
                style=(
                    discord.ButtonStyle.green
                    if str(
                        channel.overwrites_for(channel.guild.default_role).view_channel
                    )
                    == "False"
                    else discord.ButtonStyle.red
                ),
                emoji=(
                    "🙈"
                    if str(
                        channel.overwrites_for(channel.guild.default_role).view_channel
                    )
                    == "False"
                    else ""
                ),
                row=4,
            )

            hide_or_unhide_button.callback = lambda i: hide_or_unhide_button_callback(i)

            view.add_item(name_changer_button)

            view.add_item(change_bitrate_button)

            view.add_item(change_user_limit_button)

            view.add_item(transfer_ownership_button)

            view.add_item(switch_region_select)

            view.add_item(lock_or_unlock_button)

            view.add_item(hide_or_unhide_button)

            return view

        async def lock_or_unlock_button_callback(interaction: discord.Interaction):

            try:

                channel_Data = cache.j2c.get(str(interaction.channel.id))

                if not channel_Data:

                    return await interaction.response.send_message(
                        "ไม่พบข้อมูลห้อง J2C",
                        ephemeral=True,
                        delete_after=10,
                    )

                if channel_Data.get("owner_id") != interaction.user.id:

                    return await interaction.response.send_message(
                        "คุณไม่มีสิทธิ์จัดการห้องนี้",
                        ephemeral=True,
                        delete_after=10,
                    )

                if str(channel.permissions_for(channel.guild.default_role).connect) in [
                    "True",
                    "None",
                ]:

                    await channel.set_permissions(
                        channel.guild.default_role, connect=False
                    )

                    await interaction.response.send_message(
                        "ล็อกห้องแล้ว", ephemeral=True, delete_after=10
                    )

                else:

                    await channel.set_permissions(
                        channel.guild.default_role, connect=True
                    )

                    await interaction.response.send_message(
                        "ปลดล็อกห้องแล้ว", ephemeral=True, delete_after=10
                    )

            except Exception as e:

                logger.error(
                    f"Error in controller_module.lock_or_unlock_button_callback: {e}"
                )

                await interaction.response.send_message(
                    f"⚠ เกิดข้อผิดพลาดในการล็อก/ปลดล็อกห้อง: {e}",
                    ephemeral=True,
                    delete_after=10,
                )

            try:

                asyncio.create_task(update_channel())

            except Exception:
                pass

        async def hide_or_unhide_button_callback(interaction: discord.Interaction):

            try:

                channel_Data = cache.j2c.get(str(interaction.channel.id))

                if not channel_Data:

                    return await interaction.response.send_message(
                        "ไม่พบข้อมูลห้อง J2C",
                        ephemeral=True,
                        delete_after=10,
                    )

                if channel_Data.get("owner_id") != interaction.user.id:

                    return await interaction.response.send_message(
                        "คุณไม่มีสิทธิ์จัดการห้องนี้",
                        ephemeral=True,
                        delete_after=10,
                    )

                if str(
                    channel.overwrites_for(channel.guild.default_role).view_channel
                ) in ["True", "None"]:

                    await channel.set_permissions(
                        channel.guild.default_role, view_channel=False
                    )

                    await interaction.response.send_message(
                        "ซ่อนห้องแล้ว", ephemeral=True, delete_after=10
                    )

                else:

                    await channel.set_permissions(
                        channel.guild.default_role, view_channel=True
                    )

                    await interaction.response.send_message(
                        "เลิกซ่อนห้องแล้ว", ephemeral=True, delete_after=10
                    )

            except Exception as e:

                logger.error(
                    f"Error in controller_module.hide_or_unhide_button_callback: {e}"
                )

                await interaction.response.send_message(
                    f"⚠ เกิดข้อผิดพลาดในการซ่อน/เลิกซ่อนห้อง: {e}",
                    ephemeral=True,
                    delete_after=10,
                )

            try:

                asyncio.create_task(update_channel())

            except Exception:
                pass

        async def switch_region_select_callback(interaction: discord.Interaction):

            channel_Data = cache.j2c.get(str(interaction.channel.id))

            if not channel_Data:

                return await interaction.response.send_message(
                    "ไม่พบข้อมูลห้อง J2C",
                    ephemeral=True,
                    delete_after=10,
                )

            if channel_Data.get("owner_id") != interaction.user.id:

                return await interaction.response.send_message(
                    "คุณไม่มีสิทธิ์จัดการห้องนี้",
                    ephemeral=True,
                    delete_after=10,
                )

            new_region = interaction.data.get("values")[0]

            if new_region == "Automatic":

                new_region = None

            try:

                await interaction.response.defer(thinking=True, ephemeral=True)

                await channel.edit(rtc_region=new_region)

                defer_message = await interaction.edit_original_response(
                    content=f"เปลี่ยนภูมิภาคห้องเป็น `{new_region if new_region else 'Automatic'}` แล้ว",
                    view=None,
                )

                logger.info(
                    f" Channel region changed to {new_region if new_region else 'Automatic'}"
                )

                try:

                    asyncio.create_task(update_channel())

                except Exception:
                    pass

                await asyncio.sleep(10)

                try:

                    await defer_message.delete()

                except Exception:
                    pass

            except Exception as e:

                logger.error(
                    f"Error in controller_module.switch_region_select_callback: {e}"
                )

                defer_message = await interaction.edit_original_response(
                    content=f"⚠ เกิดข้อผิดพลาดในการเปลี่ยนภูมิภาคห้อง: {e}",
                    view=None,
                )

                try:

                    asyncio.create_task(update_channel())

                except Exception:
                    pass

                await asyncio.sleep(10)

                try:

                    await defer_message.delete()

                except Exception:
                    pass

        async def transfer_ownership_button_callback(interaction: discord.Interaction):

            try:

                channel_Data = cache.j2c.get(str(interaction.channel.id))

                if not channel_Data:

                    return await interaction.response.send_message(
                        "ไม่พบข้อมูลห้อง J2C",
                        ephemeral=True,
                        delete_after=10,
                    )

                if channel_Data.get("owner_id") != interaction.user.id:

                    return await interaction.response.send_message(
                        "คุณไม่มีสิทธิ์จัดการห้องนี้",
                        ephemeral=True,
                        delete_after=10,
                    )

                embed = discord.Embed(
                    title="โอนสิทธิ์เจ้าของห้อง",
                    description="เลือกผู้ใช้เพื่อโอนสิทธิ์เจ้าของภายใน 60 วินาที",
                    color=color.white,
                )

                cancled = False

                view = discord.ui.View(timeout=60)

                # user select option who are in the channel

                select_user_menu = discord.ui.UserSelect(
                    placeholder="เลือกผู้ใช้ที่จะโอนสิทธิ์ให้",
                    min_values=1,
                    max_values=1,
                )

                select_user_menu.callback = lambda i: select_user_menu_callback(i)

                async def select_user_menu_callback(interaction: discord.Interaction):

                    nonlocal cancled

                    if interaction.user.id != channel_Data.get("owner_id"):

                        return await interaction.response.send_message(
                            "คุณไม่มีสิทธิ์จัดการห้องนี้",
                            ephemeral=True,
                            delete_after=10,
                        )

                    new_owner = interaction.data.get("values")[0]

                    try:

                        new_owner = await interaction.guild.fetch_member(new_owner)

                    except Exception:
                        return await interaction.response.send_message(
                            "⚠ ไม่พบผู้ใช้ที่เลือก", ephemeral=True, delete_after=10
                        )

                    if new_owner.id == channel_Data.get("owner_id"):

                        return await interaction.response.send_message(
                            "⚠ ไม่สามารถโอนสิทธิ์ให้ตัวเองได้",
                            ephemeral=True,
                            delete_after=10,
                        )

                    if new_owner.voice == None or new_owner.voice.channel != channel:

                        return await interaction.response.send_message(
                            "⚠ ผู้ใช้ต้องอยู่ในห้องเสียงเดียวกันก่อนโอนสิทธิ์",
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.defer()

                    try:

                        await on_voice_state_update.change_j2c_owner(
                            bot, channel_Data, interaction.channel, new_owner
                        )

                        await interaction.edit_original_response(
                            content=f"โอนสิทธิ์ห้องให้ {new_owner.mention} แล้ว",
                            view=None,
                            embed=None,
                        )

                        logger.info(
                            f" Ownership of the channel has been transferred to {new_owner}"
                        )

                        await asyncio.sleep(10)

                        try:

                            await interaction.delete_original_message()

                        except Exception:
                            pass

                    except Exception as e:

                        logger.error(
                            f"Error in controller_module.transfer_ownership_button_callback.select_user_menu_callback: {e}"
                        )

                        await interaction.edit_original_response(
                            content=f"⚠ เกิดข้อผิดพลาดในการโอนสิทธิ์ห้อง: {e}",
                            view=None,
                        )

                        await asyncio.sleep(10)

                        try:

                            await interaction.delete_original_message()

                        except Exception:
                            pass

                    cancled = True

                view.add_item(select_user_menu)

                message = await interaction.response.send_message(
                    embed=embed, view=view, ephemeral=True
                )

                await asyncio.sleep(60)

                if not cancled:

                    return

                try:

                    await message.delete()

                except Exception as e:

                    logger.error(
                        f"Error in controller_module.transfer_ownership_button_callback: {e}"
                    )

            except Exception as e:

                logger.error(
                    f"Error in controller_module.transfer_ownership_button_callback: {e}"
                )

        async def change_user_limit_button_callback(interaction: discord.Interaction):

            channel_Data = cache.j2c.get(str(interaction.channel.id))

            if not channel_Data:

                return await interaction.response.send_message(
                    "ไม่พบข้อมูลห้อง J2C",
                    ephemeral=True,
                    delete_after=10,
                )

            if channel_Data.get("owner_id") != interaction.user.id:

                return await interaction.response.send_message(
                    "คุณไม่มีสิทธิ์จัดการห้องนี้",
                    ephemeral=True,
                    delete_after=10,
                )

            class ChangeUserLimit(discord.ui.Modal, title="เปลี่ยนจำนวนผู้ใช้สูงสุด"):

                new_user_limit = discord.ui.TextInput(
                    label="จำนวนผู้ใช้สูงสุดใหม่",
                    placeholder="ใส่จำนวน (0 = ไม่จำกัด)",
                    min_length=1,
                    max_length=2,
                    required=True,
                    style=discord.TextStyle.short,
                )

                async def on_submit(self, interaction: discord.Interaction):

                    if channel_Data.get("owner_id") != interaction.user.id:

                        return await interaction.response.send_message(
                            "คุณไม่มีสิทธิ์จัดการห้องนี้",
                            ephemeral=True,
                            delete_after=10,
                        )

                    new_user_limit = self.new_user_limit.value

                    try:

                        new_user_limit = int(new_user_limit)

                    except Exception:
                        return await interaction.response.send_message(
                            "⚠ จำนวนผู้ใช้ต้องเป็นตัวเลข",
                            ephemeral=True,
                            delete_after=10,
                        )

                    if new_user_limit < 0:

                        return await interaction.response.send_message(
                            "⚠ จำนวนผู้ใช้ต้องมากกว่าหรือเท่ากับ `0`",
                            ephemeral=True,
                            delete_after=10,
                        )

                    if new_user_limit == channel.user_limit:

                        return await interaction.response.send_message(
                            "⚠ จำนวนผู้ใช้เท่ากับค่าปัจจุบันอยู่แล้ว",
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.defer(thinking=True, ephemeral=True)

                    try:

                        await channel.edit(
                            user_limit=new_user_limit if new_user_limit != 0 else None
                        )

                        defer_message = await interaction.edit_original_response(
                            content=f"ตั้งจำนวนผู้ใช้สูงสุดเป็น `{new_user_limit if new_user_limit != 0 else 'ไม่จำกัด'}` แล้ว",
                            view=None,
                        )

                        try:

                            await asyncio.create_task(update_channel())

                        except Exception:
                            pass

                        logger.info(
                            f"Channel user limit changed to {new_user_limit if new_user_limit != 0 else 'Unlimited'}"
                        )

                        await asyncio.sleep(10)

                        try:

                            await defer_message.delete()

                        except Exception:
                            pass

                    except Exception as e:

                        logger.error(
                            f"Error in controller_module.change_user_limit_button_callback.ChangeUserLimit.callback: {e}"
                        )

                        defer_message = await interaction.edit_original_response(
                            content=f"⚠ เกิดข้อผิดพลาดในการตั้งจำนวนผู้ใช้สูงสุด: {e}",
                            view=None,
                        )

                        try:

                            await asyncio.create_task(update_channel())

                        except Exception:
                            pass

                        await asyncio.sleep(10)

                        try:

                            await defer_message.delete()

                        except Exception:
                            pass

            await interaction.response.send_modal(ChangeUserLimit())

        async def change_bitrate_button_callback(interaction: discord.Interaction):

            channel_Data = cache.j2c.get(str(interaction.channel.id))

            if not channel_Data:

                return await interaction.response.send_message(
                    "ไม่พบข้อมูลห้อง J2C",
                    ephemeral=True,
                    delete_after=10,
                )

            if channel_Data.get("owner_id") != interaction.user.id:

                return await interaction.response.send_message(
                    "คุณไม่มีสิทธิ์จัดการห้องนี้",
                    ephemeral=True,
                    delete_after=10,
                )

            class ChangeBitrate(discord.ui.Modal, title="เปลี่ยนบิตเรต"):

                new_bitrate_in_kbps = discord.ui.TextInput(
                    label="บิตเรตใหม่",
                    placeholder="ใส่บิตเรตใหม่ (kbps)",
                    min_length=1,
                    max_length=3,
                    required=True,
                    style=discord.TextStyle.short,
                )

                async def on_submit(self, interaction: discord.Interaction):

                    if channel_Data.get("owner_id") != interaction.user.id:

                        return await interaction.response.send_message(
                            "คุณไม่มีสิทธิ์จัดการห้องนี้",
                            ephemeral=True,
                            delete_after=10,
                        )

                    new_bitrate_in_kbps = self.new_bitrate_in_kbps.value

                    try:

                        new_bitrate_in_kbps = int(new_bitrate_in_kbps)

                    except Exception:
                        return await interaction.response.send_message(
                            "⚠ บิตเรตต้องเป็นตัวเลข",
                            ephemeral=True,
                            delete_after=10,
                        )

                    if new_bitrate_in_kbps < 8:

                        return await interaction.response.send_message(
                            "⚠ บิตเรตต้องมากกว่า `8kbps`",
                            ephemeral=True,
                            delete_after=10,
                        )

                    if (
                        new_bitrate_in_kbps
                        > int(interaction.guild.bitrate_limit) / 1000
                    ):

                        return await interaction.response.send_message(
                            f"⚠ บิตเรตสูงสุดคือ `{int(interaction.guild.bitrate_limit)/1000}kbps`",
                            ephemeral=True,
                            delete_after=10,
                        )

                    if new_bitrate_in_kbps == channel.bitrate / 1000:

                        return await interaction.response.send_message(
                            "⚠ บิตเรตเท่ากับค่าปัจจุบันอยู่แล้ว",
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.defer(thinking=True, ephemeral=True)

                    try:

                        await channel.edit(bitrate=new_bitrate_in_kbps * 1000)

                        defer_message = await interaction.edit_original_response(
                            content=f"ตั้งค่าบิตเรตเป็น `{new_bitrate_in_kbps}kbps` แล้ว",
                            view=None,
                        )

                        try:

                            await asyncio.create_task(update_channel())

                        except Exception:
                            pass

                        logger.info(
                            f" Channel bitrate changed to {new_bitrate_in_kbps}kbps"
                        )

                        await asyncio.sleep(10)

                        try:

                            await defer_message.delete()

                        except Exception:
                            pass

                    except Exception as e:

                        logger.error(
                            f"Error in controller_module.change_bitrate_button_callback.ChangeBitrate.callback: {e}"
                        )

                        defer_message = await interaction.edit_original_response(
                            content=f"⚠ เกิดข้อผิดพลาดในการเปลี่ยนบิตเรต: {e}",
                            view=None,
                        )

                        try:

                            await asyncio.create_task(update_channel())

                        except Exception:
                            pass

                        await asyncio.sleep(10)

                        try:

                            await defer_message.delete()

                        except Exception:
                            pass

            await interaction.response.send_modal(ChangeBitrate())

        async def name_changer_button_callback(interaction: discord.Interaction):

            channel_Data = cache.j2c.get(str(interaction.channel.id))

            if not channel_Data:

                return await interaction.response.send_message(
                    "ไม่พบข้อมูลห้อง J2C",
                    ephemeral=True,
                    delete_after=10,
                )

            if channel_Data.get("owner_id") != interaction.user.id:

                return await interaction.response.send_message(
                    "คุณไม่มีสิทธิ์จัดการห้องนี้",
                    ephemeral=True,
                    delete_after=10,
                )

            class ChangeChannelName(discord.ui.Modal, title="เปลี่ยนชื่อห้อง"):

                new_name = discord.ui.TextInput(
                    label="ชื่อห้องใหม่",
                    placeholder="ใส่ชื่อใหม่",
                    min_length=2,
                    max_length=100,
                    required=True,
                    style=discord.TextStyle.short,
                )

                async def on_submit(self, interaction: discord.Interaction):

                    if channel_Data.get("owner_id") != interaction.user.id:

                        return await interaction.response.send_message(
                            "คุณไม่มีสิทธิ์จัดการห้องนี้",
                            ephemeral=True,
                            delete_after=10,
                        )

                    new_name = self.new_name.value

                    if new_name == channel.name:

                        return await interaction.response.send_message(
                            "ชื่อห้องเหมือนเดิมอยู่แล้ว",
                            ephemeral=True,
                            delete_after=10,
                        )

                    await interaction.response.defer(thinking=True, ephemeral=True)

                    try:

                        await channel.edit(name=new_name)

                        defer_message = await interaction.edit_original_response(
                            content="เปลี่ยนชื่อห้องเรียบร้อยแล้ว", view=None
                        )

                        try:

                            await asyncio.create_task(update_channel())

                        except Exception:
                            pass

                        logger.info(f"Channel name changed to {new_name}")

                        await asyncio.sleep(10)

                        try:

                            await defer_message.delete()

                        except Exception:
                            pass

                    except Exception as e:

                        logger.error(
                            f"Error in controller_module.name_changer_button_callback.ChangeChannelName.callback: {e}"
                        )

                        defer_message = await interaction.edit_original_response(
                            content=f"⚠ เกิดข้อผิดพลาดในการเปลี่ยนชื่อห้อง: {e}",
                            view=None,
                        )

                        try:

                            await asyncio.create_task(update_channel())

                        except Exception:
                            pass

                        await asyncio.sleep(10)

                        try:

                            await defer_message.delete()

                        except Exception:
                            pass

            await interaction.response.send_modal(ChangeChannelName())

        embed = await panel_presenter.build_embed(channel)

        view = await get_view()

        if data.get("controller_message_id"):

            try:

                try:

                    message = await channel.fetch_message(
                        data.get("controller_message_id")
                    )

                except Exception:
                    message = None

                if not message:

                    message = await channel.send(embed=embed, view=view)

                    await j2c_db.update(
                        id=data.get("id"), controller_message_id=message.id
                    )

                else:

                    await message.edit(embed=embed, view=view)

            except Exception as e:

                pass

        else:

            try:

                message = await channel.send(embed=embed, view=view)

                await j2c_db.update(id=data.get("id"), controller_message_id=message.id)

            except Exception as e:

                pass

        async def update_channel():

            embed = await panel_presenter.build_embed(channel)

            view = await get_view()

            await message.edit(embed=embed, view=view)

    except Exception as e:

        logger.error(
            f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
        )
