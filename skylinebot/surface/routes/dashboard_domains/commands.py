from __future__ import annotations

from typing import Any, Callable


def command_catalog(
    language: str = "en",
    *,
    get_bot_fn: Callable[[], Any],
    clean_text_fn: Callable[[Any], str],
    localize_command_fn: Callable[[dict[str, Any], str], dict[str, Any]],
) -> list[dict[str, Any]]:
    get_bot = get_bot_fn
    _clean_text = clean_text_fn
    _localize_command = localize_command_fn
    bot = get_bot()
    if not bot:
        return []

    def _append_unique(target: list[str], value: str) -> None:
        cleaned = _clean_text(value).strip()
        if not cleaned:
            return
        if cleaned not in target:
            target.append(cleaned)

    def _format_slash_usage(app_cmd: Any, fallback_name: str) -> str:
        params: list[str] = []
        try:
            raw_params = getattr(app_cmd, "parameters", None)
            if isinstance(raw_params, dict):
                raw_params = list(raw_params.values())
            for param in list(raw_params or []):
                param_name = str(getattr(param, "display_name", None) or getattr(param, "name", "")).strip()
                if not param_name:
                    continue
                required = bool(getattr(param, "required", False))
                params.append(f"<{param_name}>" if required else f"[{param_name}]")
        except Exception:
            params = []
        suffix = f" {' '.join(params)}" if params else ""
        return f"/{fallback_name}{suffix}"

    commands_map: dict[str, dict[str, Any]] = {}

    def _get_entry(name: str) -> dict[str, Any]:
        key = name.strip().lower()
        if not key:
            return {}
        if key not in commands_map:
            commands_map[key] = {
                "name": key,
                "brief": "No description",
                "category": "General",
                "raw_category": "General",
                "meta": {},
                "prefix_available": False,
                "slash_available": False,
                "usage_lines": [],
                "example_lines": [],
            }
        return commands_map[key]

    try:
        prefix_commands = sorted(
            [cmd for cmd in bot.walk_commands() if str(getattr(cmd, "qualified_name", "")).strip()],
            key=lambda item: str(getattr(item, "qualified_name", "")).lower(),
        )
    except Exception:
        prefix_commands = []

    for command in prefix_commands:
        if getattr(command, "hidden", False):
            continue
        command_name = str(getattr(command, "qualified_name", "")).strip().lower()
        if not command_name:
            continue
        entry = _get_entry(command_name)
        if not entry:
            continue

        entry["prefix_available"] = True
        entry["meta"] = dict(getattr(command, "extras", {}) or entry.get("meta") or {})
        entry["brief"] = _clean_text(command.help or command.brief or entry.get("brief") or "No description")
        entry["category"] = getattr(getattr(command, "cog", None), "qualified_name", entry.get("category") or "General")
        entry["raw_category"] = entry["category"]

        signature = _clean_text(str(getattr(command, "signature", "") or "")).strip()
        prefix_usage = f"!{command_name}{(' ' + signature) if signature else ''}"
        _append_unique(entry["usage_lines"], prefix_usage)
        _append_unique(entry["example_lines"], prefix_usage)

        for alias in list(getattr(command, "aliases", []) or [])[:3]:
            alias_name = str(alias or "").strip().lower()
            if not alias_name:
                continue
            _append_unique(entry["example_lines"], f"!{alias_name}")

        app_cmd = getattr(command, "app_command", None)
        if app_cmd is not None:
            entry["slash_available"] = True
            _append_unique(entry["usage_lines"], _format_slash_usage(app_cmd, command_name))
            _append_unique(entry["example_lines"], f"/{command_name}")

    tree_commands = []
    try:
        tree_commands = sorted(
            [cmd for cmd in bot.tree.walk_commands() if str(getattr(cmd, "qualified_name", "")).strip()],
            key=lambda item: str(getattr(item, "qualified_name", "")).lower(),
        )
    except Exception:
        tree_commands = []

    for command in tree_commands:
        command_name = str(getattr(command, "qualified_name", "")).strip().lower()
        if not command_name:
            continue
        entry = _get_entry(command_name)
        if not entry:
            continue

        entry["slash_available"] = True
        if str(entry.get("brief") or "").strip() in {"", "No description"}:
            entry["brief"] = _clean_text(
                str(getattr(command, "description", None) or getattr(command, "help", None) or "No description")
            )

        binding = getattr(command, "binding", None)
        binding_name = str(getattr(binding, "qualified_name", "") or getattr(type(binding), "__name__", "") or "").strip()
        if binding_name and str(entry.get("category") or "General") == "General":
            entry["category"] = binding_name
            entry["raw_category"] = binding_name

        _append_unique(entry["usage_lines"], _format_slash_usage(command, command_name))
        _append_unique(entry["example_lines"], f"/{command_name}")

    commands_out = sorted(commands_map.values(), key=lambda item: str(item.get("name") or "").lower())
    if language == "th":
        return [_localize_command(item, "th") for item in commands_out]
    return [_localize_command(item, "en") for item in commands_out]
