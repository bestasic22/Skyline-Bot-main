from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "ai_memories"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={"created_at": NOW, "updated_at": NOW, "memory": ""},
    unique_sets=[["target_id", "type"]], # target_id can be user_id or guild_id
    json_fields=set([]),
    datetime_fields=set(["created_at", "updated_at"]),
    sequence_fields={},
    update_cache=("ai_memories_cache", ["target_id", "type"]),
    delete_cache=("ai_memories_cache", ["target_id", "type"]),
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    target_id: int = None,
    type: str = "user", # "user" or "guild"
    memory: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int = None,
    target_id: int = None,
    type: str = None,
    memory: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    target_id: int = None,
    type: str = None,
    memory: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def delete(
    id: int = None,
    target_id: int = None,
    type: str = None,
    memory: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

