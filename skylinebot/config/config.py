import os
import dotenv

# Keep process-level env (set by run_bot.ps1/run_web.ps1) as highest priority.
# This prevents .env defaults from overriding runner-selected runtime mode.
dotenv.load_dotenv(override=False)


def _apply_project_dotenv_override_for_slash_settings() -> None:
    """
    Ensure local project .env slash-command settings take precedence over stale
    user/machine environment values (common on Windows with setx).
    """
    try:
        env_path = dotenv.find_dotenv(usecwd=True)
        if not env_path:
            return
        values = dotenv.dotenv_values(env_path)
    except Exception:
        return

    for raw_key, raw_value in dict(values or {}).items():
        key = str(raw_key or "").lstrip("\ufeff").strip()
        if not key:
            continue
        if not key.startswith("SLASH_"):
            continue
        os.environ[key] = str(raw_value or "").strip()


_apply_project_dotenv_override_for_slash_settings()


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        return float(str(raw).strip())
    except Exception:
        return float(default)


def _int_env(name: str, default: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    text = str(raw).strip()
    if not text:
        return int(default)
    try:
        return int(text)
    except Exception:
        return int(default)


class BotConfigClass:
    TOKEN = (os.getenv("TOKEN") or os.getenv("\ufeffTOKEN", "")).strip()
    PREFIX = os.getenv("PREFIX", "$")
    SHARD_COUNT = int(os.getenv("SHARD_COUNT", 2))
    NAME = os.getenv("BOT_NAME", "ThunderGod")
    DASHBOARD_ENABLED = os.getenv("DASHBOARD_ENABLED", "True").lower() == "true"
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", 25572))
    WEB_SSL_ENABLED = os.getenv("WEB_SSL_ENABLED", "False").lower() == "true"
    WEB_SSL_CERTFILE = os.getenv("WEB_SSL_CERTFILE", "").strip()
    WEB_SSL_KEYFILE = os.getenv("WEB_SSL_KEYFILE", "").strip()
    WEB_SSL_KEYFILE_PASSWORD = os.getenv("WEB_SSL_KEYFILE_PASSWORD", "").strip()
    WEB_SSL_CA_CERTS = os.getenv("WEB_SSL_CA_CERTS", "").strip()
    DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
    DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
    DISCORD_APPLICATION_PUBLIC_KEY = (
        os.getenv("DISCORD_APPLICATION_PUBLIC_KEY", "")
        or os.getenv("DISCORD_PUBLIC_KEY", "")
    ).strip()
    DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "")
    RUNTIME_CONTROL_TOKEN = (
        os.getenv("RUNTIME_CONTROL_TOKEN", "") or os.getenv("DASHBOARD_SECRET", "")
    ).strip()
    DASHBOARD_BASE_URL = str(
        os.getenv("DASHBOARD_BASE_URL", f"http://localhost:{WEB_PORT}") or ""
    ).strip().rstrip("/")
    API_HOST = WEB_HOST
    API_PORT = WEB_PORT
    SYNC_EMOJIS = os.getenv("SYNC_EMOJIS", "True").lower() == "true"
    SYNC_EMOJIS_AFTER_READY = os.getenv("SYNC_EMOJIS_AFTER_READY", "True").lower() == "true"
    SYNC_EMOJIS_START_DELAY_SECONDS = float(os.getenv("SYNC_EMOJIS_START_DELAY_SECONDS", "45"))
    DONATE_FREE_ADS_ENABLED = os.getenv("DONATE_FREE_ADS_ENABLED", "True").lower() == "true"
    GOOGLE_ADSENSE_CLIENT_ID = os.getenv("GOOGLE_ADSENSE_CLIENT_ID", "").strip()
    GOOGLE_ADSENSE_DONATE_SLOT = os.getenv("GOOGLE_ADSENSE_DONATE_SLOT", "").strip()
    GOOGLE_ADSENSE_PUBLISHER_ID = os.getenv("GOOGLE_ADSENSE_PUBLISHER_ID", "").strip()
    GOOGLE_ADS_TXT_LINES = os.getenv("GOOGLE_ADS_TXT_LINES", "").strip()
    GOOGLE_SITE_VERIFICATION = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
    DISCORD_GATEWAY_LOG_MODE = str(
        os.getenv("DISCORD_GATEWAY_LOG_MODE", "shard") or "shard"
    ).strip().lower()
    DISCORD_GATEWAY_LOG_COOLDOWN_SECONDS = _float_env(
        "DISCORD_GATEWAY_LOG_COOLDOWN_SECONDS", 45.0
    )
    DISCORD_GATEWAY_STARTUP_DISCONNECT_GRACE_SECONDS = _float_env(
        "DISCORD_GATEWAY_STARTUP_DISCONNECT_GRACE_SECONDS", 45.0
    )


class urls:
    gif_api_base = "https://tenor.googleapis.com/v2/search"
    gif_api_key = "AIzaSyBx9qncGCjblFYGOfyqta6WUoYJTOtK5Co"


class channels:
    report_channel = _int_env("REPORT_CHANNEL", 0)
    support_report_channel = _int_env("SUPPORT_REPORT_CHANNEL_ID", report_channel)
    guild_join_webhook = os.getenv("GUILD_JOIN_WEBHOOK", "")
    guild_leave_webhook = os.getenv("GUILD_LEAVE_WEBHOOK", "")
    shards_log_webhook = os.getenv("SHARDS_LOG_WEBHOOK", "")


_dev_env = os.getenv("DEVELOPER_IDS", "870179991462236170, 767979794411028491")
_dev_parsed = [int(u.strip()) for u in _dev_env.split(",") if u.strip().isdigit()]

class users:
    developer = tuple(_dev_parsed)
    root = list(_dev_parsed)


class Types:

    redeem_code_types = {
        "silver_guild_preminum": "Silver Guild Premium",
        "golden_guild_premium": "Gole Guild Premium",
        "diamond_guild_premium": "Diamond Guild Premium",
        "permanent_guild_premium": "Permanent Guild Premium",
        "user_no_prefix": "User No Prefix",
    }


class storage:
    def __init__(self):
        self.uri = os.getenv("MONGO_SRV") or os.getenv("MONGO_URI", "")
        self.uri_backup = os.getenv("MONGO_URI_BACKUP", "")
        self.name = os.getenv("MONGO_NAME", "")


class database(storage):
    pass
