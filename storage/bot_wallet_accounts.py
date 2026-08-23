from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "bot_wallet_accounts"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "balance": 0.0,
        "locked_balance": 0.0,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["user_id"]],
    json_fields=set([]),
    datetime_fields=set(["created_at", "updated_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


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

