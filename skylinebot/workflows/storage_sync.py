import asyncio

import storage

from skylinebot.bridge.storage import ping as storage_ping
from skylinebot.console.logging import logger


async def load_storage():
    try:
        await storage_ping()
    except Exception as error:
        logger.error(f"MongoDB preflight failed: {error}")
        raise

    tasks = [
        storage.guilds.create_table(),
        storage.guilds_log.create_table(),
        storage.users.create_table(),
        storage.guild_user_profiles.create_table(),
        storage.j2c.create_table(),
        storage.j2c_settings.create_table(),
        storage.antinuke_settings.create_table(),
        storage.antinuke_bypass.create_table(),
        storage.welcomer_settings.create_table(),
        storage.guilds_backup.create_table(),
        storage.redeem_codes.create_table(),
        storage.afk.create_table(),
        storage.snipe_data.create_table(),
        storage.ignore_data.create_table(),
        storage.ban_data.create_table(),
        storage.command_access.create_table(),
        storage.automod.create_table(),
        storage.custom_roles.create_table(),
        storage.custom_roles_permissions.create_table(),
        storage.media_channels.create_table(),
        storage.auto_responder.create_table(),
        storage.giveaways.create_table(),
        storage.giveaway_participants.create_table(),
        storage.giveaways_permissions.create_table(),
        storage.fun_rooms.create_table(),
        storage.ticket_settings.create_table(),
        storage.tickets.create_table(),
        storage.shop.create_table(),
        storage.shop_settings.create_table(),
        storage.shop_products.create_table(),
        storage.shop_orders.create_table(),
        storage.music.create_table(),
        storage.music_user_playlists.create_table(),
        storage.promote_channels.create_table(),
        storage.promote_history.create_table(),
        storage.promote_web_queue.create_table(),
        storage.user_reminders.create_table(),
        storage.ai_chat_channels.create_table(),
        storage.ai_memories.create_table(),
        storage.activity_sessions.create_table(),
        storage.activity_panels.create_table(),
        storage.image_ocr_settings.create_table(),
        storage.server_stats.create_table(),
        storage.donate_settings.create_table(),
        storage.donatebot_verify_logs.create_table(),
        storage.bot_wallet_accounts.create_table(),
        storage.bot_wallet_ledger.create_table(),
        storage.bot_payment_sessions.create_table(),
        storage.bot_plan_subscriptions.create_table(),
        storage.bot_user_app_subscriptions.create_table(),
        storage.bot_billing_events.create_table(),
        storage.economy_settings.create_table(),
        storage.economy_wallets.create_table(),
        storage.economy_audit.create_table(),
        storage.levels_users.create_table(),
        storage.invite_members.create_table(),
        storage.invite_stats.create_table(),
        storage.ops_hub_records.create_table(),
        storage.photoroom_channels.create_table(),
        storage.photo_assets.create_table(),
        storage.photo_asset_blobs.create_table(),
        storage.dashboard_image_assets.create_table(),
        storage.dashboard_image_original_meta.create_table(),
        storage.dashboard_image_usage_refs.create_table(),
        storage.rp_settings.create_table(),
        storage.rp_characters.create_table(),
        storage.rp_scenarios.create_table(),
        storage.rp_events.create_table(),
        storage.rp_permissions.create_table(),
        storage.rp_audit_logs.create_table(),
        storage.rp_schedules.create_table(),
        storage.rp_economy_guard.create_table(),
        storage.rp_event_history.create_table(),
        storage.rp_scenario_stats.create_table(),
    ]
    await asyncio.gather(*tasks)
    logger.database("Database collections loaded")


loadDataBase = load_storage
