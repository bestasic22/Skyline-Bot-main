# Dashboard Route Map

This index shows which route is registered in which file and where the implementation lives.

## assets.py

- Register file: `skylinebot/surface/routes/dashboard_pages/assets.py`
- Implementation file: `skylinebot/surface/routes/dashboard_pages/assets_impl.py`

- `GET` `/assets/music-idle` -> `dashboard_music_idle_image`
- `GET` `/assets/donate/{filename:path}` -> `dashboard_donate_asset`
- `GET` `/assets/verify/{filename:path}` -> `dashboard_verify_asset`
- `GET` `/assets/welcome/{filename:path}` -> `dashboard_welcome_asset`
- `GET` `/assets/starboard/{filename:path}` -> `dashboard_starboard_asset`
- `GET` `/assets/embed/{filename:path}` -> `dashboard_embed_asset`
- `GET` `/assets/promote/{filename:path}` -> `dashboard_promote_asset`
- `GET` `/assets/db/{asset_key}` -> `dashboard_db_asset`
- `GET` `/assets/db/{asset_key}/{filename:path}` -> `dashboard_db_asset`

## public.py

- Register file: `skylinebot/surface/routes/dashboard_pages/public.py`
- Implementation file: `skylinebot/surface/routes/dashboard_pages/public_impl.py`

- `GET` `/careers` -> `dashboard_careers_page`
- `GET` `/premium` -> `dashboard_premium_page`
- `GET` `/subscribe-plan` -> `dashboard_subscribe_plan_page`
- `GET` `` -> `dashboard_home`
- `GET` `/home` -> `dashboard_landing_home`
- `GET` `/commands` -> `dashboard_commands_index`
- `GET` `/invite` -> `dashboard_invite_hub`
- `GET` `/donatebot` -> `dashboard_donatebot_hub`
- `GET` `/wallet` -> `dashboard_wallet_page`
- `POST` `/wallet/topup` -> `dashboard_wallet_create_topup`
- `POST` `/wallet/topup/verify` -> `dashboard_wallet_verify_topup`
- `GET` `/wallet/topup/status` -> `dashboard_wallet_topup_status`
- `POST` `/topup` -> `dashboard_wallet_create_topup`
- `POST` `/topup/verify` -> `dashboard_wallet_verify_topup`
- `GET` `/topup/status` -> `dashboard_wallet_topup_status`
- `POST` `/topurp` -> `dashboard_wallet_create_topup`
- `POST` `/topurp/verify` -> `dashboard_wallet_verify_topup`
- `GET` `/topurp/status` -> `dashboard_wallet_topup_status`
- `POST` `/wallet/plan/subscribe` -> `dashboard_wallet_subscribe_plan`
- `POST` `/wallet/plan/cancel` -> `dashboard_wallet_cancel_plan`
- `GET` `/donate-wallet` -> `dashboard_donate_wallet_page`
- `POST` `/donate-wallet/create` -> `dashboard_donate_wallet_create`
- `POST` `/donate-wallet/verify` -> `dashboard_donate_wallet_verify`
- `POST` `/payments/webhook/confirm` -> `dashboard_payment_webhook_confirm`
- `GET` `/status` -> `dashboard_system_status`
- `GET` `/status/live` -> `dashboard_system_status_live`
- `POST` `/donatebot/verify` -> `dashboard_donatebot_verify`
- `GET` `/contag` -> `dashboard_contag_alias`
- `GET` `/None` -> `dashboard_none_fallback`
- `GET` `/redeem` -> `dashboard_redeem_page`
- `POST` `/redeem` -> `dashboard_redeem_submit`
- `GET` `/docs` -> `dashboard_docs_page`
- `GET` `/personalizer` -> `dashboard_personalizer_page`
- `GET` `/invitebot` -> `dashboard_invitebot_page`
- `GET` `/rule` -> `dashboard_rule_page`
- `GET` `/rule/bot` -> `dashboard_rule_bot_page`
- `GET` `/rule/serversupport` -> `dashboard_rule_server_support_page`
- `GET` `/interactions-endpoint` -> `dashboard_interactions_endpoint_page`
- `GET` `/linked-role-verify` -> `dashboard_linked_role_verify_page`
- `GET` `/privacy` -> `dashboard_privacy_page`
- `GET` `/privacy-policy` -> `dashboard_privacy_policy_page`
- `GET` `/terms` -> `dashboard_terms_page`
- `GET` `/terms-of-service` -> `dashboard_terms_of_service_page`
- `GET` `/bug-bounty` -> `dashboard_bug_bounty_legacy_redirect`
- `GET` `/contact` -> External redirect (`https://niceshopallforme.web.app/contact`)
- `POST` `/contact/*` -> External redirect (`https://niceshopallforme.web.app/contact`)
- `GET` `/plugins/moderation` -> `dashboard_plugins_moderation_page`
- `GET` `/plugins/utilities` -> `dashboard_plugins_utilities_page`
- `GET` `/plugins/social-alerts` -> `dashboard_plugins_social_alerts_page`
- `GET` `/plugins/games-fun` -> `dashboard_plugins_games_fun_page`
- `GET` `/report` -> `dashboard_report_page`
- `POST` `/report` -> `dashboard_report_submit`
- `GET` `/guides/ticket` -> `dashboard_guide_ticket_page`
- `GET` `/guides/security` -> `dashboard_guide_security_page`
- `GET` `/guides/giveaways` -> `dashboard_guide_giveaways_page`
- `GET` `/guides/promote` -> `dashboard_guide_promote_page`
- `GET` `/guides/guildstyle-roles` -> `dashboard_guide_guildstyle_roles_page`
- `GET` `/SetingProfileUser` -> `dashboard_user_profile_settings`
- `GET` `/setting-profile-user` -> `dashboard_user_profile_settings`
- `GET` `/SetingProfileUser/topup-history` -> `dashboard_user_profile_topup_history`
- `GET` `/setting-profile-user/topup-history` -> `dashboard_user_profile_topup_history`
- `GET` `/SetingProfileUser/premium-history` -> `dashboard_user_profile_premium_history`
- `GET` `/setting-profile-user/premium-history` -> `dashboard_user_profile_premium_history`
- `GET` `/login` -> `dashboard_login`
- `GET` `/auth/callback` -> `dashboard_callback`
- `GET` `/logout` -> `dashboard_logout`

## admin.py

- Register file: `skylinebot/surface/routes/dashboard_pages/admin.py`
- Implementation file: `skylinebot/surface/routes/dashboard_pages/admin_impl.py`

- `GET` `/admin/trusted-servers` -> `dashboard_trusted_servers_manager`
- `GET` `/admin/donatebot/verify-logs` -> `dashboard_admin_donatebot_verify_logs`
- `GET` `/admin/billing/history` -> `dashboard_admin_billing_history`
- `POST` `/admin/trusted-servers` -> `dashboard_trusted_servers_manager_save`
- `GET` `/admin/ownerbot` -> `dashboard_ownerbot_console`
- `GET` `/admin/ownerbot/settings` -> `dashboard_ownerbot_settings`
- `GET` `/admin/ownerbot/settings/runtime/{runtime_page}` -> `dashboard_ownerbot_settings_runtime_page`
- `GET` `/admin/ownerbot/settings/{section}` -> `dashboard_ownerbot_settings_section`
- `GET` `/admin/ownerbot/commands` -> `dashboard_ownerbot_command_catalog`
- `GET` `/admin/ownerbot/assets` -> `dashboard_ownerbot_asset_stats`
- `POST` `/admin/ownerbot/assets/cleanup` -> `dashboard_ownerbot_asset_cleanup`
- `POST` `/admin/ownerbot/runtime` -> `dashboard_ownerbot_update_runtime`
- `POST` `/admin/ownerbot/payment-provider` -> `dashboard_ownerbot_update_payment_provider`
- `POST` `/admin/ownerbot/upload-channels` -> `dashboard_ownerbot_update_upload_channels`
- `POST` `/admin/ownerbot/upload-channels/create` -> `dashboard_ownerbot_create_upload_channels`
- `POST` `/admin/ownerbot/redeem/generate` -> `dashboard_ownerbot_generate_redeem`
- `POST` `/admin/ownerbot/redeem/update` -> `dashboard_ownerbot_update_redeem`
- `POST` `/admin/ownerbot/guild` -> `dashboard_ownerbot_update_guild_plan`
- `POST` `/admin/ownerbot/user-wallet` -> `dashboard_ownerbot_update_user_wallet`

## guild.py

- Register file: `skylinebot/surface/routes/dashboard_pages/guild.py`
- Implementation file: `skylinebot/surface/routes/dashboard_pages/guild_impl.py`

- `GET` `/guild/{guild_id}` -> `dashboard_overview`
- `GET` `/guild/{guild_id}/live` -> `dashboard_live`
- `GET` `/guild/{guild_id}/live/options` -> `dashboard_live_options`
- `GET` `/donate/{guild_id}` -> `dashboard_public_donate`
- `GET` `/guild/{guild_id}/{tab}` -> `dashboard_tab`
- `POST` `/guild/{guild_id}/general` -> `update_general_settings`
- `POST` `/guild/{guild_id}/bot_profile` -> `update_bot_profile_settings`
- `POST` `/guild/{guild_id}/security` -> `update_security_settings`
- `POST` `/guild/{guild_id}/moderation` -> `update_moderation_settings`
- `POST` `/guild/{guild_id}/screening_categories` -> `update_screening_categories_settings`
- `POST` `/guild/{guild_id}/colors` -> `update_color_sets_settings`
- `POST` `/guild/{guild_id}/colors/apply_set` -> `apply_color_set_now`
- `POST` `/guild/{guild_id}/levels` -> `update_levels_settings`
- `POST` `/guild/{guild_id}/economy` -> `update_economy_settings`
- `POST` `/guild/{guild_id}/roleplay` -> `update_roleplay_settings`
- `GET` `/guild/{guild_id}/roleplay/export` -> `export_roleplay_config`
- `POST` `/guild/{guild_id}/reaction_roles` -> `update_reaction_roles_settings`
- `POST` `/guild/{guild_id}/starboard` -> `update_starboard_settings`
- `POST` `/guild/{guild_id}/embed_messages` -> `update_embed_messages_settings`
- `POST` `/guild/{guild_id}/embed_messages/send` -> `send_embed_message_from_dashboard`
- `POST` `/guild/{guild_id}/autoresponder/add` -> `add_autoresponder`
- `POST` `/guild/{guild_id}/autoresponder/delete` -> `delete_autoresponder`
- `POST` `/guild/{guild_id}/customrole/add` -> `add_customrole`
- `POST` `/guild/{guild_id}/customrole/delete` -> `delete_customrole`
- `POST` `/guild/{guild_id}/music` -> `update_music_settings`
- `POST` `/guild/{guild_id}/temp_channels` -> `update_temp_channels_settings`
- `POST` `/guild/{guild_id}/temp_channels/send_interface` -> `send_temp_channels_interface`
- `POST` `/guild/{guild_id}/music/control` -> `music_web_control`
- `POST` `/guild/{guild_id}/promote/send` -> `promote_web_send`
- `POST` `/guild/{guild_id}/promote/settings` -> `promote_web_update_settings`
- `POST` `/guild/{guild_id}/temp_links/settings` -> `update_temp_links_settings`
- `POST` `/guild/{guild_id}/temp_links/create` -> `create_temp_link`
- `POST` `/guild/{guild_id}/commands/toggle` -> `toggle_command`
- `POST` `/guild/{guild_id}/giveaways` -> `update_giveaway_settings`
- `POST` `/guild/{guild_id}/giveaways/create` -> `create_giveaway_from_web`
- `POST` `/guild/{guild_id}/tickets` -> `update_ticket_settings`
- `POST` `/guild/{guild_id}/welcome` -> `update_welcomer_settings`
- `POST` `/guild/{guild_id}/welcomer` -> `update_welcomer_settings`
- `POST` `/guild/{guild_id}/leaver` -> `update_welcomer_settings`
- `POST` `/guild/{guild_id}/ocr` -> `update_ocr_settings`
- `POST` `/guild/{guild_id}/server_stats` -> `update_server_stats`
- `POST` `/guild/{guild_id}/donate` -> `update_donate_settings`
- `POST` `/guild/{guild_id}/donate/slip` -> `upload_donate_slip`
- `POST` `/guild/{guild_id}/donate/slip/{slip_id}/status` -> `update_donate_slip_status`
- `GET` `/guild/{guild_id}/donate/slips.json` -> `donate_slips_live_data`
- `POST` `/guild/{guild_id}/alerts` -> `update_alerts_settings`
- `POST` `/guild/{guild_id}/alerts/test` -> `test_alerts_settings_now`
- `POST` `/guild/{guild_id}/verify` -> `update_verify_settings`
- `POST` `/guild/{guild_id}/aichat` -> `update_aichat_settings`
- `POST` `/guild/{guild_id}/aichat/clear` -> `clear_aichat_memories`
- `POST` `/guild/{guild_id}/server_stats/delete_all` -> `delete_all_server_stats`
- `POST` `/guild/{guild_id}/media/add` -> `add_media_channel`
- `POST` `/guild/{guild_id}/media/delete` -> `delete_media_channel`
