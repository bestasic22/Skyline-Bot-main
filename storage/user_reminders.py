from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "reminders"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "status": "pending",
        "retry_count": 0,
        "created_at": NOW,
        "updated_at": NOW,
    },
    unique_sets=[],
    json_fields=set([]),
    datetime_fields=set(["remind_at", "created_at", "updated_at", "sent_at", "cancelled_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    user_id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    message: str = None,
    status: str = None,
    retry_count: int = None,
    last_error: str = None,
    remind_at: str = None,
    sent_at: str = None,
    cancelled_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    user_id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    message: str = None,
    status: str = None,
    retry_count: int = None,
    last_error: str = None,
    remind_at: str = None,
    sent_at: str = None,
    cancelled_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    user_id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    message: str = None,
    status: str = None,
    retry_count: int = None,
    last_error: str = None,
    remind_at: str = None,
    sent_at: str = None,
    cancelled_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    user_id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    message: str = None,
    status: str = None,
    retry_count: int = None,
    last_error: str = None,
    remind_at: str = None,
    sent_at: str = None,
    cancelled_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    user_id: int = None,
    guild_id: int = None,
    channel_id: int = None,
    message: str = None,
    status: str = None,
    retry_count: int = None,
    last_error: str = None,
    remind_at: str = None,
    sent_at: str = None,
    cancelled_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

