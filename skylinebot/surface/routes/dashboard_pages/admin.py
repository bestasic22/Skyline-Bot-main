from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .admin_impl import (
    dashboard_trusted_servers_manager,
    dashboard_admin_donatebot_verify_logs,
    dashboard_trusted_servers_manager_save,
    dashboard_ownerbot_console,
    dashboard_ownerbot_settings,
    dashboard_ownerbot_settings_runtime_page,
    dashboard_ownerbot_settings_section,
    dashboard_ownerbot_console_live,
    dashboard_ownerbot_command_catalog,
    dashboard_ownerbot_update_status,
    dashboard_ownerbot_update_runtime,
    dashboard_ownerbot_update_promote_policy,
    dashboard_ownerbot_manage_promote_suspension,
    dashboard_ownerbot_update_mongo_settings,
    dashboard_ownerbot_mongo_cleanup,
    dashboard_ownerbot_mongo_migrate,
    dashboard_ownerbot_mongo_history_manage,
    dashboard_ownerbot_asset_stats,
    dashboard_ownerbot_asset_cleanup,
    dashboard_ownerbot_send_discordbotlist_vote_embed,
    dashboard_ownerbot_update_payment_provider,
    dashboard_ownerbot_update_plan_pricing,
    dashboard_ownerbot_update_upload_channels,
    dashboard_ownerbot_create_upload_channels,
    dashboard_ownerbot_generate_redeem,
    dashboard_ownerbot_update_redeem,
    dashboard_ownerbot_update_guild_plan,
    dashboard_ownerbot_update_user_wallet,
)
from .billing_impl import dashboard_admin_billing_history


def register(router: APIRouter) -> None:
    router.add_api_route("/admin/trusted-servers", dashboard_trusted_servers_manager, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/donatebot/verify-logs", dashboard_admin_donatebot_verify_logs, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/billing/history", dashboard_admin_billing_history, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/trusted-servers", dashboard_trusted_servers_manager_save, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot", dashboard_ownerbot_console, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/settings", dashboard_ownerbot_settings, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/settings/runtime/{runtime_page}", dashboard_ownerbot_settings_runtime_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/settings/{section}", dashboard_ownerbot_settings_section, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/live", dashboard_ownerbot_console_live, methods=["GET"])
    router.add_api_route("/admin/ownerbot/commands", dashboard_ownerbot_command_catalog, methods=["GET"])
    router.add_api_route("/admin/ownerbot/status", dashboard_ownerbot_update_status, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/runtime", dashboard_ownerbot_update_runtime, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/promote/policy", dashboard_ownerbot_update_promote_policy, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/promote/suspension", dashboard_ownerbot_manage_promote_suspension, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/vote/send-embed", dashboard_ownerbot_send_discordbotlist_vote_embed, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/mongo/settings", dashboard_ownerbot_update_mongo_settings, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/mongo/cleanup", dashboard_ownerbot_mongo_cleanup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/mongo/migrate", dashboard_ownerbot_mongo_migrate, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/mongo/history/manage", dashboard_ownerbot_mongo_history_manage, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/assets", dashboard_ownerbot_asset_stats, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/assets/cleanup", dashboard_ownerbot_asset_cleanup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/payment-provider", dashboard_ownerbot_update_payment_provider, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/plan-pricing", dashboard_ownerbot_update_plan_pricing, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/upload-channels", dashboard_ownerbot_update_upload_channels, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/upload-channels/create", dashboard_ownerbot_create_upload_channels, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/redeem/generate", dashboard_ownerbot_generate_redeem, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/redeem/update", dashboard_ownerbot_update_redeem, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/guild", dashboard_ownerbot_update_guild_plan, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/admin/ownerbot/user-wallet", dashboard_ownerbot_update_user_wallet, methods=["POST"], response_class=HTMLResponse)
