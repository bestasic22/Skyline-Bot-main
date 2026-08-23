from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "economy_audit"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "action": "unknown",
        "location": "cash",
        "amount": 0,
        "before_cash": 0,
        "before_bank": 0,
        "after_cash": 0,
        "after_bank": 0,
        "note": "",
        "created_at": NOW,
    },
    unique_sets=[],
    json_fields=set([]),
    datetime_fields=set(["created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    actor_id: int = None,
    target_user_id: int = None,
    action: str = None,
    location: str = None,
    amount: int = None,
    before_cash: int = None,
    before_bank: int = None,
    after_cash: int = None,
    after_bank: int = None,
    note: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    user_id: int = None,
    actor_id: int = None,
    target_user_id: int = None,
    action: str = None,
    location: str = None,
    amount: int = None,
    before_cash: int = None,
    before_bank: int = None,
    after_cash: int = None,
    after_bank: int = None,
    note: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    actor_id: int = None,
    target_user_id: int = None,
    action: str = None,
    location: str = None,
    amount: int = None,
    before_cash: int = None,
    before_bank: int = None,
    after_cash: int = None,
    after_bank: int = None,
    note: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    actor_id: int = None,
    target_user_id: int = None,
    action: str = None,
    location: str = None,
    amount: int = None,
    before_cash: int = None,
    before_bank: int = None,
    after_cash: int = None,
    after_bank: int = None,
    note: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    actor_id: int = None,
    target_user_id: int = None,
    action: str = None,
    location: str = None,
    amount: int = None,
    before_cash: int = None,
    before_bank: int = None,
    after_cash: int = None,
    after_bank: int = None,
    note: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

