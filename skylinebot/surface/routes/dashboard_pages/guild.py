from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .guild_impl import (
    dashboard_music_user,
    dashboard_music_user_live,
    dashboard_music_user_live_options,
    dashboard_overview,
    dashboard_live,
    dashboard_live_options,
    dashboard_emoji_picker_payload,
    dashboard_public_donate,
    dashboard_promote_history_redirect,
    dashboard_set_access_mode,
    dashboard_tab,
    upload_dashboard_image_asset,
    update_general_settings,
    update_bot_profile_settings,
    update_security_settings,
    update_moderation_settings,
    update_screening_categories_settings,
    update_color_sets_settings,
    apply_color_set_now,
    update_levels_settings,
    update_economy_settings,
    update_roleplay_settings,
    update_guildstyle_studio_settings,
    export_roleplay_config,
    update_reaction_roles_settings,
    update_starboard_settings,
    update_embed_messages_settings,
    send_embed_message_from_dashboard,
    add_autoresponder,
    delete_autoresponder,
    add_customrole,
    update_customrole,
    set_customrole_required_role,
    clear_customrole_required_role,
    delete_customrole,
    update_music_settings,
    update_temp_channels_settings,
    send_temp_channels_interface,
    music_web_control,
    music_web_control_user,
    promote_web_send,
    promote_web_update_settings,
    update_temp_links_settings,
    create_temp_link,
    toggle_command,
    update_giveaway_settings,
    create_giveaway_from_web,
    update_ticket_settings,
    update_shop_settings,
    update_welcomer_settings,
    update_ocr_settings,
    update_server_stats,
    update_donate_settings,
    upload_donate_slip,
    update_donate_slip_status,
    donate_slips_live_data,
    update_alerts_settings,
    test_alerts_settings_now,
    update_voice_randomizer_settings,
    update_verify_settings,
    update_aichat_settings,
    clear_aichat_memories,
    delete_all_server_stats,
    add_media_channel,
    delete_media_channel,
)


def register(router: APIRouter) -> None:
    router.add_api_route("/music/{guild_id}", dashboard_music_user, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/music/{guild_id}/live", dashboard_music_user_live, methods=["GET"])
    router.add_api_route("/music/{guild_id}/live/options", dashboard_music_user_live_options, methods=["GET"])
    router.add_api_route("/music/{guild_id}/control", music_web_control_user, methods=["POST"])
    router.add_api_route("/guild/{guild_id}", dashboard_overview, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/guild/{guild_id}/live", dashboard_live, methods=["GET"])
    router.add_api_route("/guild/{guild_id}/live/options", dashboard_live_options, methods=["GET"])
    router.add_api_route("/guild/{guild_id}/emoji-picker", dashboard_emoji_picker_payload, methods=["GET"])
    router.add_api_route("/guild/{guild_id}/access/mode", dashboard_set_access_mode, methods=["GET"])
    router.add_api_route("/donate/{guild_id}", dashboard_public_donate, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/guild/{guild_id}/promote/history", dashboard_promote_history_redirect, methods=["GET"])
    router.add_api_route("/guild/{guild_id}/{tab}", dashboard_tab, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/guild/{guild_id}/upload-image", upload_dashboard_image_asset, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/general", update_general_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/bot_profile", update_bot_profile_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/security", update_security_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/moderation", update_moderation_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/screening_categories", update_screening_categories_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/colors", update_color_sets_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/colors/apply_set", apply_color_set_now, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/levels", update_levels_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/economy", update_economy_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/roleplay", update_roleplay_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/guildstyle_studio", update_guildstyle_studio_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/roleplay/export", export_roleplay_config, methods=["GET"])
    router.add_api_route("/guild/{guild_id}/reaction_roles", update_reaction_roles_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/starboard", update_starboard_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/embed_messages", update_embed_messages_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/embed_messages/send", send_embed_message_from_dashboard, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/autoresponder/add", add_autoresponder, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/autoresponder/delete", delete_autoresponder, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/customrole/add", add_customrole, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/customrole/update", update_customrole, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/customrole/required_role", set_customrole_required_role, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/customrole/required_role/clear", clear_customrole_required_role, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/customrole/delete", delete_customrole, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/music", update_music_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/temp_channels", update_temp_channels_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/temp_channels/send_interface", send_temp_channels_interface, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/music/control", music_web_control, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/promote/send", promote_web_send, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/promote/settings", promote_web_update_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/temp_links/settings", update_temp_links_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/temp_links/create", create_temp_link, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/commands/toggle", toggle_command, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/giveaways", update_giveaway_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/giveaways/create", create_giveaway_from_web, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/tickets", update_ticket_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/shop", update_shop_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/welcome", update_welcomer_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/welcomer", update_welcomer_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/leaver", update_welcomer_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/ocr", update_ocr_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/server_stats", update_server_stats, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/donate", update_donate_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/donate/slip", upload_donate_slip, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/donate/slip/{slip_id}/status", update_donate_slip_status, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/donate/slips.json", donate_slips_live_data, methods=["GET"])
    router.add_api_route("/guild/{guild_id}/alerts", update_alerts_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/alerts/test", test_alerts_settings_now, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/voice_randomizer", update_voice_randomizer_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/verify", update_verify_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/aichat", update_aichat_settings, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/aichat/clear", clear_aichat_memories, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/server_stats/delete_all", delete_all_server_stats, methods=["POST"])
    router.add_api_route("/guild/{guild_id}/media/add", add_media_channel, methods=["POST"], include_in_schema=False)
    router.add_api_route("/guild/{guild_id}/media/delete", delete_media_channel, methods=["POST"], include_in_schema=False)
