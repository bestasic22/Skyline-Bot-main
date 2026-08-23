from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuildTabRenderContext:
    session: dict[str, Any]
    guilds: list[dict[str, Any]]
    current_guild: dict[str, Any]
    bot_guild: Any
    state: dict[str, Any]
    notice: str | None = None
