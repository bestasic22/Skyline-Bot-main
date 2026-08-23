from datetime import datetime, timezone

from skylinebot.bridge.storage import get_collection
from storage.engine import CollectionStore

COLLECTION_NAME = "dashboard_config"

CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={},
    unique_sets=[["config_key"]],
    json_fields=set([]),
    datetime_fields=set([]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    config_key: str = None,
    config_value: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    config_key: str = None,
    config_value: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    config_key: str = None,
    config_value: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    config_key: str = None,
    config_value: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    config_key: str = None,
    config_value: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()


async def set_config_value(config_key: str, config_value: str):
    key = str(config_key or "").strip()
    if not key:
        raise ValueError("config_key is required")

    now = datetime.now(timezone.utc)
    collection = await get_collection(COLLECTION_NAME)

    # Update every matching row across clusters to prevent stale reads in aggregate mode.
    result = await collection.update_many(
        {"config_key": key},
        {"$set": {"config_value": str(config_value or ""), "updated_at": now}},
    )
    matched_count = int(getattr(result, "matched_count", 0) or 0)
    if matched_count <= 0:
        await insert(config_key=key, config_value=str(config_value or ""), updated_at=now)
    return await get(config_key=key)
