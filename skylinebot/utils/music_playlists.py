from __future__ import annotations

import datetime
import re
from typing import Any

import storage.music_user_playlists

MAX_USER_PLAYLISTS = 25
MAX_ITEMS_PER_PLAYLIST = 50
MAX_PLAYLIST_NAME_LENGTH = 60
MAX_ITEM_TEXT_LENGTH = 380

_THAI_CHAR_START = ord("\u0E00")
_THAI_CHAR_END = ord("\u0E7F")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_SPACE_RE = re.compile(r"[\s_./|:;,+]+")
_DASH_RE = re.compile(r"-{2,}")


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _is_thai_char(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return _THAI_CHAR_START <= code <= _THAI_CHAR_END


def _sanitize_text(raw_value: Any, *, max_length: int) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return ""
    return text[: max(1, int(max_length))]


def _safe_limit(raw_value: Any, default_value: int) -> int:
    try:
        parsed = int(raw_value)
    except Exception:
        parsed = int(default_value)
    return max(1, parsed)


def _safe_int(raw_value: Any, *, default_value: int = 0) -> int:
    try:
        return int(raw_value)
    except Exception:
        return int(default_value)


def looks_like_url(value: Any) -> bool:
    return bool(_URL_RE.match(str(value or "").strip()))


def slugify_playlist_key(raw_name: Any) -> str:
    text = str(raw_name or "").strip().lower()
    text = _SPACE_RE.sub("-", text).strip("-")
    if not text:
        return "playlist"
    out_chars: list[str] = []
    for ch in text:
        if ch == "-":
            out_chars.append(ch)
            continue
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or _is_thai_char(ch):
            out_chars.append(ch)
    slug = _DASH_RE.sub("-", "".join(out_chars)).strip("-")
    if not slug:
        return "playlist"
    return slug[:42]


def normalize_playlist_item(raw_item: Any) -> dict[str, Any] | None:
    kind = ""
    if isinstance(raw_item, dict):
        raw_value = raw_item.get("value")
        kind = str(raw_item.get("kind") or "").strip().lower()
    else:
        raw_value = raw_item
    value = _sanitize_text(raw_value, max_length=MAX_ITEM_TEXT_LENGTH)
    if not value:
        return None
    if kind not in {"url", "query"}:
        kind = "url" if looks_like_url(value) else "query"
    return {"kind": kind, "value": value}


def normalize_playlist_items(raw_items: Any, *, limit: int = MAX_ITEMS_PER_PLAYLIST) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in list(raw_items or []):
        normalized = normalize_playlist_item(raw_item)
        if not normalized:
            continue
        dedupe_key = str(normalized.get("value") or "").strip().casefold()
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(normalized)
        if len(out) >= max(1, int(limit)):
            break
    return out


def normalize_playlist_row(row: dict[str, Any] | None) -> dict[str, Any]:
    src = dict(row or {})
    slug = slugify_playlist_key(src.get("slug") or src.get("name") or "")
    name = _sanitize_text(
        src.get("name") or slug.replace("-", " ").title(),
        max_length=MAX_PLAYLIST_NAME_LENGTH,
    )
    items = normalize_playlist_items(src.get("items") or [])
    src["slug"] = slug
    src["name"] = name
    src["items"] = items
    src["item_count"] = len(items)
    src["user_id"] = _safe_int(src.get("user_id"))
    return src


async def list_user_playlists(user_id: int) -> list[dict[str, Any]]:
    uid = _safe_int(user_id)
    if uid <= 0:
        return []

    # Read by both numeric/string user_id for legacy rows and then hard-filter
    # by owner_id to prevent cross-user data leakage.
    raw_rows: list[dict[str, Any]] = []
    seen_raw_ids: set[int] = set()
    for filter_user_id in (uid, str(uid)):
        fetched_rows = await storage.music_user_playlists.gets(user_id=filter_user_id)
        for row in list(fetched_rows or []):
            if not row:
                continue
            row_id = _safe_int(row.get("id"))
            if row_id > 0 and row_id in seen_raw_ids:
                continue
            if row_id > 0:
                seen_raw_ids.add(row_id)
            raw_rows.append(row)

    normalized: list[dict[str, Any]] = []
    for row in raw_rows:
        normalized_row = normalize_playlist_row(row)
        if _safe_int(normalized_row.get("user_id")) != uid:
            continue
        normalized.append(normalized_row)

    normalized.sort(key=lambda row: _safe_int(row.get("id")))
    return normalized


def _find_playlist_from_rows(rows: list[dict[str, Any]], key: Any) -> dict[str, Any] | None:
    key_text = str(key or "").strip()
    if not key_text:
        return None
    key_lower = key_text.casefold()
    if key_text.isdigit():
        wanted_id = int(key_text)
        for row in rows:
            if int(row.get("id", 0) or 0) == wanted_id:
                return row
    for row in rows:
        if str(row.get("slug") or "").casefold() == key_lower:
            return row
    for row in rows:
        if str(row.get("name") or "").casefold() == key_lower:
            return row
    return None


async def get_user_playlist(user_id: int, key: Any) -> dict[str, Any] | None:
    rows = await list_user_playlists(user_id)
    return _find_playlist_from_rows(rows, key)


async def create_user_playlist(
    user_id: int,
    name: Any,
    *,
    max_playlists: int = MAX_USER_PLAYLISTS,
) -> tuple[bool, str, dict[str, Any] | None]:
    uid = int(user_id)
    rows = await list_user_playlists(uid)
    max_playlist_count = _safe_limit(max_playlists, MAX_USER_PLAYLISTS)
    if len(rows) >= max_playlist_count:
        return (
            False,
            f"You can create up to {max_playlist_count} playlists per account.",
            None,
        )

    requested_name = _sanitize_text(name, max_length=MAX_PLAYLIST_NAME_LENGTH)
    if not requested_name:
        requested_name = f"Playlist {len(rows) + 1}"

    base_slug = slugify_playlist_key(requested_name)
    existing_slugs = {str(row.get("slug") or "") for row in rows}
    slug = base_slug
    suffix = 2
    while slug in existing_slugs:
        suffix_tail = f"-{suffix}"
        slug = f"{base_slug[: max(1, 42 - len(suffix_tail))]}{suffix_tail}"
        suffix += 1
        if suffix > 999:
            return False, "Could not generate a unique playlist slug.", None

    created = await storage.music_user_playlists.insert(
        user_id=uid,
        slug=slug,
        name=requested_name,
        items=[],
        updated_at=_utc_now(),
    )
    return True, f"Created playlist: {requested_name}", normalize_playlist_row(created)


async def delete_user_playlist(user_id: int, key: Any) -> tuple[bool, str]:
    playlist = await get_user_playlist(user_id, key)
    if not playlist:
        return False, "Playlist not found."
    deleted_rows = await storage.music_user_playlists.delete(id=int(playlist["id"]))
    if not deleted_rows:
        return False, "Playlist not found."
    return True, f"Deleted playlist: {playlist.get('name')}"


async def add_item_to_playlist(
    user_id: int,
    playlist_key: Any,
    item_value: Any,
    *,
    max_items_per_playlist: int = MAX_ITEMS_PER_PLAYLIST,
) -> tuple[bool, str, dict[str, Any] | None]:
    playlist = await get_user_playlist(user_id, playlist_key)
    if not playlist:
        return False, "Playlist not found.", None

    normalized_item = normalize_playlist_item(item_value)
    if not normalized_item:
        return False, "Please provide a valid song name or URL.", playlist

    max_item_count = _safe_limit(max_items_per_playlist, MAX_ITEMS_PER_PLAYLIST)
    items = normalize_playlist_items(playlist.get("items") or [], limit=max_item_count)
    if len(items) >= max_item_count:
        return (
            False,
            f"This playlist already reached {max_item_count} items.",
            playlist,
        )

    normalized_value = str(normalized_item.get("value") or "").casefold()
    for existing_item in items:
        if str(existing_item.get("value") or "").casefold() == normalized_value:
            return False, "This song/url is already in the playlist.", playlist

    items.append(normalized_item)
    updated = await storage.music_user_playlists.update(
        id=int(playlist["id"]),
        items=items,
        updated_at=_utc_now(),
    )
    normalized = normalize_playlist_row(updated)
    return True, f"Added item to {normalized.get('name')}.", normalized


async def remove_items_from_playlist(
    user_id: int,
    playlist_key: Any,
    indexes: list[int],
) -> tuple[bool, str, dict[str, Any] | None, int]:
    playlist = await get_user_playlist(user_id, playlist_key)
    if not playlist:
        return False, "Playlist not found.", None, 0

    items = normalize_playlist_items(playlist.get("items") or [])
    if not items:
        return False, "Playlist is empty.", playlist, 0

    wanted_indexes: set[int] = set()
    for raw_index in list(indexes or []):
        try:
            index = int(raw_index)
        except Exception:
            continue
        if 1 <= index <= len(items):
            wanted_indexes.add(index)
    if not wanted_indexes:
        return False, "No valid item index to remove.", playlist, 0

    kept_items: list[dict[str, Any]] = []
    removed_count = 0
    for idx, item in enumerate(items, start=1):
        if idx in wanted_indexes:
            removed_count += 1
            continue
        kept_items.append(item)

    updated = await storage.music_user_playlists.update(
        id=int(playlist["id"]),
        items=kept_items,
        updated_at=_utc_now(),
    )
    normalized = normalize_playlist_row(updated)
    return True, f"Removed {removed_count} item(s) from {normalized.get('name')}.", normalized, removed_count


async def mark_playlist_used(user_id: int, playlist_key: Any) -> dict[str, Any] | None:
    playlist = await get_user_playlist(user_id, playlist_key)
    if not playlist:
        return None
    updated = await storage.music_user_playlists.update(
        id=int(playlist["id"]),
        last_used_at=_utc_now(),
    )
    return normalize_playlist_row(updated)
