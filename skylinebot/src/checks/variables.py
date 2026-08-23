import datetime
import discord


def _safe_replace(text: str, token: str, value) -> str:
    if value is None:
        return text
    return text.replace(token, str(value))


def fetch_variables(
    text: str,
    member: discord.Member = None,
    guild: discord.Guild = None,
    channel=None,
    extra: dict | None = None,
):
    if not text:
        return None

    if member:
        text = _safe_replace(text, "{user}", member.display_name)
        text = _safe_replace(text, "{user.id}", member.id)
        text = _safe_replace(text, "{user.tag}", member.discriminator)
        text = _safe_replace(text, "{user.mention}", member.mention)
        text = _safe_replace(text, "{user.avatar}", member.display_avatar.url)
        text = _safe_replace(
            text, "{user.created_at}", f"<t:{int(member.created_at.timestamp())}:R>"
        )
        if member.joined_at:
            text = _safe_replace(
                text, "{user.joined_at}", f"<t:{int(member.joined_at.timestamp())}:R>"
            )

    if guild:
        text = _safe_replace(text, "{guild}", guild.name)
        text = _safe_replace(text, "{server}", guild.name)
        text = _safe_replace(text, "{server.id}", guild.id)
        if guild.icon:
            text = _safe_replace(text, "{server.icon}", guild.icon.url)
        text = _safe_replace(text, "{guild.id}", guild.id)
        if guild.icon:
            text = _safe_replace(text, "{guild.icon}", guild.icon.url)
        if guild.owner:
            text = _safe_replace(text, "{guild.owner}", guild.owner.display_name)
            text = _safe_replace(text, "{guild.owner.id}", guild.owner.id)
        text = _safe_replace(text, "{member.count}", guild.member_count)

    if channel:
        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            raw_channel = str(channel or "").strip()
            if raw_channel.isdigit():
                channel_id = int(raw_channel)
        channel_name = getattr(channel, "name", None)
        channel_mention = f"<#{int(channel_id)}>" if channel_id else None

        text = _safe_replace(text, "{channel}", channel_mention)
        text = _safe_replace(text, "{channel.mention}", channel_mention)
        text = _safe_replace(text, "{channel.id}", channel_id)
        text = _safe_replace(text, "{channel.name}", channel_name)

        text = _safe_replace(text, "{welcome.channel}", channel_mention)
        text = _safe_replace(text, "{welcome.channel.mention}", channel_mention)
        text = _safe_replace(text, "{welcome.channel.id}", channel_id)

        text = _safe_replace(text, "{room}", channel_mention)
        text = _safe_replace(text, "{room.id}", channel_id)

    if isinstance(extra, dict):
        for raw_key, raw_value in extra.items():
            token_name = str(raw_key or "").strip()
            if not token_name:
                continue
            if token_name.startswith("{") and token_name.endswith("}") and len(token_name) >= 2:
                token_name = token_name[1:-1].strip()
            if not token_name:
                continue
            text = _safe_replace(text, "{" + token_name + "}", raw_value)
            text = _safe_replace(text, "{{" + token_name + "}}", raw_value)

    text = _safe_replace(
        text, "{time}", f"{datetime.datetime.utcnow().strftime('%H:%M:%S %d-%m-%Y')} UTC"
    )
    text = text.replace(r"\n", "\n")
    return text
