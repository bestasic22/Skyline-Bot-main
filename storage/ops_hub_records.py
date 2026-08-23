from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "ops_hub_records"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={"status": "active", "data": {}, "created_at": NOW, "updated_at": NOW},
    unique_sets=[["guild_id", "kind", "key"]],
    json_fields={"data"},
    datetime_fields={"created_at", "updated_at"},
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    kind: str = None,
    key: str = None,
    status: str = None,
    actor_id: int = None,
    user_id: int = None,
    reference_id: int = None,
    data=None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int = None,
    guild_id: int = None,
    kind: str = None,
    key: str = None,
    status: str = None,
    actor_id: int = None,
    user_id: int = None,
    reference_id: int = None,
    data=None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    kind: str = None,
    key: str = None,
    status: str = None,
    actor_id: int = None,
    user_id: int = None,
    reference_id: int = None,
    data=None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    kind: str = None,
    key: str = None,
    status: str = None,
    actor_id: int = None,
    user_id: int = None,
    reference_id: int = None,
    data=None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    kind: str = None,
    key: str = None,
    status: str = None,
    actor_id: int = None,
    user_id: int = None,
    reference_id: int = None,
    data=None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
