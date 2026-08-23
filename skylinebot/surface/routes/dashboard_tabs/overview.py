from __future__ import annotations

from typing import Any
from .. import dashboard_core as core


def _overview_metrics(current_guild: dict[str, Any], state: dict[str, Any], bot_guild) -> dict[str, int]:
    _core = core
    cache = _core.cache
    active_giveaways = len(cache.giveaways.get(str(bot_guild.id), {}))
    ticket_modules = state["ticket_modules"]
    welcomer = state["welcomer"]
    automod = state["automod"]
    antinuke = state["antinuke"]
    return {
        "security": sum(
            1
            for key in (
                "anti_bot_add",
                "anti_channel_delete",
                "anti_role_delete",
                "anti_webhook_create",
                "anti_everyone_mention",
            )
            if antinuke.get(key)
        ),
        "moderation": sum(1 for key in ("antilink_enabled", "antispam_enabled", "antibadwords_enabled") if automod.get(key)),
        "tickets": sum(1 for module in ticket_modules if module.get("enabled")),
        "giveaways": active_giveaways,
        "welcomer": sum(1 for key in ("welcome", "welcome_message", "welcome_embed", "autorole", "leave") if welcomer.get(key)),
        "commands": len(state["command_access"].get("disabled_commands", []) or []),
    }


def _render_overview(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "overview",
) -> str:
    _core = core
    dashboard_activity = _core.dashboard_activity
    _overview_activity_periods = _core._overview_activity_periods
    json = _core.json
    datetime = _core.datetime
    discord = _core.discord
    _escape = _core._escape
    _with_cache_bust = _core._with_cache_bust
    _discord_default_avatar_url = _core._discord_default_avatar_url
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_layout = _core._render_layout

    bot_member_count = 0
    human_member_count = 0
    total_member_count = 0
    presence_counts = {"online": 0, "idle": 0, "dnd": 0, "offline": 0, "other": 0}
    channel_counts = {"total": 0, "category": 0, "chat": 0, "voice": 0, "other": 0}

    guild_icon_raw = str(getattr(getattr(bot_guild, "icon", None), "url", "") or current_guild.get("icon") or "").strip()
    if not guild_icon_raw:
        guild_icon_raw = _discord_default_avatar_url(current_guild.get("id", "0"))
    guild_icon_url = _escape(_with_cache_bust(guild_icon_raw, bucket_seconds=300))

    owner_id = 0
    owner_member = None
    guild_owner_text = "Unknown"
    guild_owner_id_text = "-"
    guild_created_text = "-"
    guild_age_text = "-"
    bkk_tz = datetime.timezone(datetime.timedelta(hours=7))

    try:
        owner_id = int(getattr(bot_guild, "owner_id", 0) or 0) if bot_guild else 0
    except Exception:
        owner_id = 0
    try:
        owner_member = getattr(bot_guild, "owner", None) if bot_guild else None
        if owner_member is None and owner_id and bot_guild:
            owner_member = bot_guild.get_member(owner_id)
    except Exception:
        owner_member = None

    owner_name_raw = str(
        getattr(owner_member, "display_name", None)
        or getattr(owner_member, "name", None)
        or ""
    ).strip()
    if owner_name_raw:
        guild_owner_text = _escape(owner_name_raw)
    elif owner_id > 0:
        guild_owner_text = f"User ID {owner_id}"
    guild_owner_id_text = _escape(str(owner_id)) if owner_id > 0 else "-"

    guild_created_dt = getattr(bot_guild, "created_at", None) if bot_guild else None
    if guild_created_dt is None:
        try:
            guild_created_dt = discord.utils.snowflake_time(int(current_guild.get("id")))
        except Exception:
            guild_created_dt = None
    if guild_created_dt is not None:
        try:
            if guild_created_dt.tzinfo is None:
                guild_created_dt = guild_created_dt.replace(tzinfo=datetime.timezone.utc)
            guild_created_text = _escape(guild_created_dt.astimezone(bkk_tz).strftime("%d/%m/%Y %H:%M"))
            age_days = max(
                0,
                int(
                    (
                        datetime.datetime.now(tz=datetime.timezone.utc)
                        - guild_created_dt.astimezone(datetime.timezone.utc)
                    ).total_seconds()
                    // 86400
                ),
            )
            guild_age_text = _escape(f"{age_days:,} วัน")
        except Exception:
            guild_created_text = "-"
            guild_age_text = "-"

    try:
        members = list(getattr(bot_guild, "members", []) or []) if bot_guild else []
        for member in members:
            is_bot = bool(getattr(member, "bot", False))
            if is_bot:
                bot_member_count += 1
            else:
                human_member_count += 1
                status_raw = str(getattr(member, "status", "offline") or "offline").strip().lower()
                if status_raw.startswith("status."):
                    status_raw = status_raw.split(".", 1)[1]
                if status_raw in {"online", "idle", "dnd", "offline"}:
                    presence_counts[status_raw] += 1
                else:
                    presence_counts["other"] += 1
        if members:
            total_member_count = int(getattr(bot_guild, "member_count", 0) or len(members) or 0)
    except Exception:
        bot_member_count = 0
        human_member_count = 0
        total_member_count = 0
        presence_counts = {"online": 0, "idle": 0, "dnd": 0, "offline": 0, "other": 0}

    try:
        channels = list(getattr(bot_guild, "channels", []) or []) if bot_guild else []
        for channel in channels:
            ctype = str(getattr(channel, "type", "") or "").strip().lower()
            channel_counts["total"] += 1
            if ctype == "category":
                channel_counts["category"] += 1
            elif ctype in {"voice", "stage_voice"}:
                channel_counts["voice"] += 1
            elif ctype in {"text", "news", "forum", "public_thread", "private_thread", "news_thread"}:
                channel_counts["chat"] += 1
            else:
                channel_counts["other"] += 1
    except Exception:
        channel_counts = {"total": 0, "category": 0, "chat": 0, "voice": 0, "other": 0}

    if human_member_count <= 0:
        human_member_count = max(0, int(current_guild.get("members") or 0) - bot_member_count)
    if total_member_count <= 0:
        total_member_count = int(current_guild.get("members") or 0)
    if total_member_count <= 0 and (human_member_count or bot_member_count):
        total_member_count = int(human_member_count + bot_member_count)
    if channel_counts["total"] <= 0:
        channel_counts["total"] = int(current_guild.get("channels") or 0)
    if sum(presence_counts.values()) <= 0 and human_member_count > 0:
        presence_counts["offline"] = int(human_member_count)

    history = dashboard_activity.get_history(int(current_guild["id"]))
    period_payload = _overview_activity_periods(history, current_member_count=total_member_count)
    payload_today = period_payload.get("today", {})
    messages_24h = int(payload_today.get("messages_total") or 0)
    joins_24h = int(payload_today.get("joins_total") or 0)
    leaves_24h = int(payload_today.get("leaves_total") or 0)
    overview_payload_json = json.dumps(period_payload, ensure_ascii=False)

    body = _render_dashboard_f_template("overview.html", locals())
    return _render_layout(
        title=f"SkylineBOT Overview - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
