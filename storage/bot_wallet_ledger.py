from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "bot_wallet_ledger"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "amount": 0.0,
        "balance_before": 0.0,
        "balance_after": 0.0,
        "kind": "unknown",
        "source_mode": "topup",
        "meta": {},
        "created_at": NOW,
    },
    unique_sets=[],
    json_fields=set(["meta"]),
    datetime_fields=set(["created_at"]),
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

