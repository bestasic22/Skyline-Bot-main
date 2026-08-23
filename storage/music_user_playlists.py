from __future__ import annotations

from skylinebot.bridge.storage import get_collection
from skylinebot.console.logging import logger
from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "music_user_playlists"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "name": "",
        "items": [],
        "created_at": NOW,
        "updated_at": NOW,
        "last_used_at": NOW,
    },
    unique_sets=[["user_id", "slug"]],
    json_fields={"items"},
    datetime_fields={"created_at", "updated_at", "last_used_at"},
    sequence_fields={},
)


async def create_table():
    await _store.prepare()
    await _drop_legacy_unique_user_index()


async def _drop_legacy_unique_user_index() -> None:
    """
    Remove legacy unique index on `user_id` (single-field) so one user can own
    multiple playlists. Current uniqueness must be (`user_id`, `slug`).
    """
    try:
        collection = await get_collection(COLLECTION_NAME)
        index_info = await collection.index_information()
    except Exception as error:
        logger.warning(f"music_user_playlists index inspection failed: {error}")
        return

    for index_name, payload in dict(index_info or {}).items():
        if index_name == "_id_":
            continue
        if not bool((payload or {}).get("unique")):
            continue
        keys = [str(field) for field, _direction in list((payload or {}).get("key") or [])]
        if keys != ["user_id"]:
            continue
        try:
            await collection.drop_index(index_name)
            logger.info(
                f"Removed legacy unique index `{index_name}` from {COLLECTION_NAME} "
                "(single-field `user_id`)."
            )
        except Exception as error:
            logger.warning(f"Failed dropping legacy index `{index_name}` on {COLLECTION_NAME}: {error}")


async def insert(**kwargs):
    return await _store.insert(kwargs)


async def update(id: int, **kwargs):
    return await _store.update({"id": id, **kwargs})


async def get(**kwargs):
    return await _store.get(kwargs)


async def gets(**kwargs):
    return await _store.gets(kwargs)


async def delete(**kwargs):
    return await _store.delete(kwargs)


async def get_all():
    return await _store.get_all()


async def count(**kwargs):
    return await _store.count(kwargs)
