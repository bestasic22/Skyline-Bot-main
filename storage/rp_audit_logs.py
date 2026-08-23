from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_audit_logs"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "actor_user_id": 0,
        "actor_name": "",
        "action": "",
        "scope": "config",
        "note": "",
        "snapshot_before": {},
        "snapshot_after": {},
        "created_at": NOW,
    },
    unique_sets=[],
    json_fields=set(["snapshot_before", "snapshot_after"]),
    datetime_fields=set(["created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    actor_user_id: int = None,
    actor_name: str = None,
    action: str = None,
    scope: str = None,
    note: str = None,
    snapshot_before: dict = None,
    snapshot_after: dict = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    actor_user_id: int = None,
    actor_name: str = None,
    action: str = None,
    scope: str = None,
    note: str = None,
    snapshot_before: dict = None,
    snapshot_after: dict = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    actor_user_id: int = None,
    actor_name: str = None,
    action: str = None,
    scope: str = None,
    note: str = None,
    snapshot_before: dict = None,
    snapshot_after: dict = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    actor_user_id: int = None,
    actor_name: str = None,
    action: str = None,
    scope: str = None,
    note: str = None,
    snapshot_before: dict = None,
    snapshot_after: dict = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    actor_user_id: int = None,
    actor_name: str = None,
    action: str = None,
    scope: str = None,
    note: str = None,
    snapshot_before: dict = None,
    snapshot_after: dict = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()


async def delete_limited(limit: int, filters: dict | None = None):
    return await _store.delete_limited(limit, filters or {})
