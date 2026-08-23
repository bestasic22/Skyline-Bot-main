from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Callable

from .context import GuildTabRenderContext

TAB_RENDER_MODULES: dict[str, str] = {
    "overview": "overview",
    "server_settings": "server_settings",
    "embed_messages": "embed_messages",
    "premium_receive": "premium_receive",
    "tools": "tools",
    "welcome_center": "welcome_center",
    "auto_reply_center": "auto_reply_center",
    "economy": "economy",
    "roleplay": "roleplay",
    "guildstyle_studio": "guildstyle_studio",
    "levels": "levels",
    "autoroles": "autoroles",
    "colors": "colors",
    "reaction_roles": "reaction_roles",
    "starboard": "starboard",
    "temp_channels": "temp_channels",
    "join_to_create": "join_to_create",
    "temp_links": "temp_links",
    "statistics_plus": "statistics_plus",
    "screening": "screening",
    "screening_categories": "screening_categories",
    "automation": "automation",
    "anti_raid": "anti_raid",
    "extra_protection": "extra_protection",
    "alerts_twitch": "alerts_twitch",
    "alerts_youtube": "alerts_youtube",
    "alerts_tiktok": "alerts_tiktok",
    "alerts_github": "alerts_github",
    "alerts_facebook": "alerts_facebook",
    "control_panel": "control_panel",
    "audit_logs": "audit_logs",
    "security": "security",
    "moderation": "moderation",
    "music": "music",
    "promote": "promote",
    "commands": "commands",
    "logs": "logs",
    "giveaways": "giveaways",
    "tickets": "tickets",
    "shop": "shop",
    "welcome": "welcome",
    "leaver": "leaver",
    "ocr": "ocr",
    "verify": "verify",
    "voice_randomizer": "voice_randomizer",
    "aichat": "aichat",
    "media": "media",
    "autoresponder": "autoresponder",
    "customrole": "customrole",
    "server_stats": "server_stats",
    "donate": "donate",
    "alerts": "alerts",
}


@lru_cache(maxsize=256)
def _resolve_render_function(slug: str) -> Callable[[GuildTabRenderContext], str] | None:
    normalized_slug = str(slug or "").strip().lower()
    module_name = TAB_RENDER_MODULES.get(normalized_slug)
    if not module_name:
        return None
    module = import_module(f"{__package__}.{module_name}")
    render_fn = getattr(module, "render", None)
    if not callable(render_fn):
        return None
    return render_fn


def build_dashboard_tab_renderers(context: GuildTabRenderContext) -> dict[str, Callable[[], str]]:
    renderers: dict[str, Callable[[], str]] = {}
    for slug in TAB_RENDER_MODULES:
        render_fn = _resolve_render_function(slug)
        if render_fn is None:
            continue
        renderers[slug] = (lambda fn=render_fn: fn(context))
    return renderers


def render_dashboard_tab(slug: str, context: GuildTabRenderContext) -> str | None:
    render_fn = _resolve_render_function(slug)
    if render_fn is None:
        return None
    return render_fn(context)
