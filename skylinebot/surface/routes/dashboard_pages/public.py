from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from .public_impl import (
    dashboard_careers_page,
    dashboard_premium_page,
    dashboard_subscribe_plan_page,
    dashboard_home,
    dashboard_landing_home,
    dashboard_home_legacy_redirect,
    dashboard_commands_index,
    dashboard_commands_help_page,
    dashboard_commands_help_legacy_redirect,
    dashboard_invite_hub,
    dashboard_donatebot_hub,
    dashboard_donate_page,
    dashboard_system_status,
    dashboard_system_status_live,
    dashboard_runtime_discord,
    dashboard_runtime_control,
    dashboard_discordbotlist_vote_webhook,
    dashboard_donatebot_verify,
    dashboard_contag_alias,
    dashboard_none_fallback,
    dashboard_redeem_page,
    dashboard_redeem_submit,
    dashboard_docs_page,
    dashboard_leaderboard_page,
    dashboard_personalizer_page,
    dashboard_tags_page,
    dashboard_invitebot_page,
    dashboard_rule_page,
    dashboard_rule_bot_page,
    dashboard_rule_server_support_page,
    dashboard_server_support_page,
    dashboard_support_page,
    dashboard_interactions_endpoint_page,
    dashboard_linked_role_verify_page,
    dashboard_verify_session_page,
    dashboard_verify_session_submit,
    dashboard_privacy_page,
    dashboard_privacy_policy_page,
    dashboard_terms_page,
    dashboard_terms_of_service_page,
    dashboard_bug_bounty_legacy_redirect,
    dashboard_plugins_moderation_page,
    dashboard_plugins_utilities_page,
    dashboard_plugins_social_alerts_page,
    dashboard_plugins_games_fun_page,
    dashboard_report_page,
    dashboard_report_submit,
    dashboard_guide_ticket_page,
    dashboard_guide_security_page,
    dashboard_guide_giveaways_page,
    dashboard_guide_promote_page,
    dashboard_guide_guildstyle_roles_page,
    dashboard_studio_split_preview_page,
    dashboard_user_profile_settings,
    dashboard_user_profile_topup_history,
    dashboard_user_profile_premium_history,
    dashboard_public_user_profile,
    dashboard_login,
    dashboard_callback,
    dashboard_logout,
)
from .billing_impl import (
    dashboard_wallet_page,
    dashboard_wallet_create_topup,
    dashboard_wallet_verify_topup,
    dashboard_wallet_topup_status,
    dashboard_wallet_subscribe_plan,
    dashboard_wallet_cancel_plan,
    dashboard_wallet_subscribe_user_app_plan,
    dashboard_wallet_cancel_user_app_plan,
    dashboard_donate_wallet_page,
    dashboard_donate_wallet_create,
    dashboard_donate_wallet_verify,
    dashboard_payment_webhook_confirm,
)
from skylinebot.style import urls as style_urls


CONTACT_EXTERNAL_URL = str(style_urls.CONTACT or "https://niceshopallforme.web.app/contact").strip()


async def _contact_external_redirect(thread_key: str = "", message_id: int = 0):
    _ = thread_key, message_id
    return RedirectResponse(CONTACT_EXTERNAL_URL, status_code=303)


def register(router: APIRouter) -> None:
    router.add_api_route("/careers", dashboard_careers_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/premium", dashboard_premium_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/subscribe-plan", dashboard_subscribe_plan_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("", dashboard_home, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/home", dashboard_home_legacy_redirect, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/commands", dashboard_commands_index, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/commands-help", dashboard_commands_help_legacy_redirect, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/invite", dashboard_invite_hub, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/donate", dashboard_donate_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/donatebot", dashboard_donatebot_hub, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/wallet", dashboard_wallet_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/wallet/topup", dashboard_wallet_create_topup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/wallet/topup/verify", dashboard_wallet_verify_topup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/wallet/topup/status", dashboard_wallet_topup_status, methods=["GET"])
    router.add_api_route("/topup", dashboard_wallet_create_topup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/topup/verify", dashboard_wallet_verify_topup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/topup/status", dashboard_wallet_topup_status, methods=["GET"])
    router.add_api_route("/topurp", dashboard_wallet_create_topup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/topurp/verify", dashboard_wallet_verify_topup, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/topurp/status", dashboard_wallet_topup_status, methods=["GET"])
    router.add_api_route("/wallet/plan/subscribe", dashboard_wallet_subscribe_plan, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/wallet/plan/cancel", dashboard_wallet_cancel_plan, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/wallet/app-user/subscribe", dashboard_wallet_subscribe_user_app_plan, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/wallet/app-user/cancel", dashboard_wallet_cancel_user_app_plan, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/donate-wallet", dashboard_donate_wallet_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/donate-wallet/create", dashboard_donate_wallet_create, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/donate-wallet/verify", dashboard_donate_wallet_verify, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/payments/webhook/confirm", dashboard_payment_webhook_confirm, methods=["POST"])
    router.add_api_route("/votes/discordbotlist/webhook", dashboard_discordbotlist_vote_webhook, methods=["POST"])
    router.add_api_route("/status", dashboard_system_status, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/status/live", dashboard_system_status_live, methods=["GET"])
    router.add_api_route("/runtime/discord", dashboard_runtime_discord, methods=["GET"])
    router.add_api_route("/runtime/control", dashboard_runtime_control, methods=["GET"])
    router.add_api_route("/runtime/control", dashboard_runtime_control, methods=["POST"])
    router.add_api_route("/donatebot/verify", dashboard_donatebot_verify, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/contag", dashboard_contag_alias, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/None", dashboard_none_fallback, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/redeem", dashboard_redeem_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/redeem", dashboard_redeem_submit, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/docs", dashboard_docs_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/leaderboard", dashboard_leaderboard_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/tags", dashboard_tags_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/personalizer", dashboard_personalizer_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/invitebot", dashboard_invitebot_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/rule", dashboard_rule_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/rule/bot", dashboard_rule_bot_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/rule/serversupport", dashboard_rule_server_support_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/support", dashboard_support_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/serversupport", dashboard_server_support_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/ServerSupport", dashboard_server_support_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/server-support", dashboard_server_support_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/interactions-endpoint", dashboard_interactions_endpoint_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/linked-role-verify", dashboard_linked_role_verify_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/verify/session", dashboard_verify_session_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/verify/session", dashboard_verify_session_submit, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/privacy", dashboard_privacy_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/privacy-policy", dashboard_privacy_policy_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/terms", dashboard_terms_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/terms-of-service", dashboard_terms_of_service_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/bug-bounty", dashboard_bug_bounty_legacy_redirect, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/contact", _contact_external_redirect, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/contact/realtime/threads", _contact_external_redirect, methods=["GET"])
    router.add_api_route("/contact/realtime/thread/{thread_key}/messages", _contact_external_redirect, methods=["GET"])
    router.add_api_route("/contact/realtime/thread/{thread_key}/message", _contact_external_redirect, methods=["POST"])
    router.add_api_route("/contact/realtime/thread/{thread_key}/toggle", _contact_external_redirect, methods=["POST"])
    router.add_api_route("/contact/thread/create", _contact_external_redirect, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/contact/thread/{thread_key}/message", _contact_external_redirect, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/contact/thread/{thread_key}/toggle", _contact_external_redirect, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/contact/message/{message_id}/delete", _contact_external_redirect, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/plugins/moderation", dashboard_plugins_moderation_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/plugins/utilities", dashboard_plugins_utilities_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/plugins/social-alerts", dashboard_plugins_social_alerts_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/plugins/games-fun", dashboard_plugins_games_fun_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/report", dashboard_report_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/report", dashboard_report_submit, methods=["POST"], response_class=HTMLResponse)
    router.add_api_route("/guides/ticket", dashboard_guide_ticket_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/guides/security", dashboard_guide_security_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/guides/giveaways", dashboard_guide_giveaways_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/guides/promote", dashboard_guide_promote_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/guides/guildstyle-roles", dashboard_guide_guildstyle_roles_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/studio-split-preview", dashboard_studio_split_preview_page, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/SetingProfileUser", dashboard_user_profile_settings, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/setting-profile-user", dashboard_user_profile_settings, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/SetingProfileUser/topup-history", dashboard_user_profile_topup_history, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/setting-profile-user/topup-history", dashboard_user_profile_topup_history, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/SetingProfileUser/premium-history", dashboard_user_profile_premium_history, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/setting-profile-user/premium-history", dashboard_user_profile_premium_history, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/user-profile/{guild_id}/{user_id}", dashboard_public_user_profile, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/profile/{guild_id}/{user_id}", dashboard_public_user_profile, methods=["GET"], response_class=HTMLResponse)
    router.add_api_route("/login", dashboard_login, methods=["GET"])
    router.add_api_route("/auth/callback", dashboard_callback, methods=["GET"])
    router.add_api_route("/logout", dashboard_logout, methods=["GET"])
