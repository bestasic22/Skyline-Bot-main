from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "promote_web_queue"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "status": "pending",
        "attempts": 0,
        "payload": {},
        "error": "",
        "created_at": NOW,
        "updated_at": NOW,
    },
    json_fields=set(["payload"]),
    datetime_fields=set(["created_at", "updated_at"]),
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    payload: dict = None,
    status: str = None,
    attempts: int = None,
    error: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    user_id: int = None,
    payload: dict = None,
    status: str = None,
    attempts: int = None,
    error: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    payload: dict = None,
    status: str = None,
    attempts: int = None,
    error: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    payload: dict = None,
    status: str = None,
    attempts: int = None,
    error: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    payload: dict = None,
    status: str = None,
    attempts: int = None,
    error: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
