from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "ai_chat_channels"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={"created_at": NOW, "reply_chance": 100},
    unique_sets=[["guild_id"]],
    json_fields=set([]),
    datetime_fields=set(["created_at"]),
    sequence_fields={},
    update_cache=("ai_chat_channels_cache", ["guild_id"]),
    delete_cache=("ai_chat_channels_cache", ["guild_id"]),
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    ai_model: str = None,
    reply_chance: int = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    channel_id: int = None,
    ai_model: str = None,
    reply_chance: int = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    ai_model: str = None,
    reply_chance: int = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    ai_model: str = None,
    reply_chance: int = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    ai_model: str = None,
    reply_chance: int = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

