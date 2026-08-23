from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "invite_members"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "guild_id": None,
        "user_id": None,
        "inviter_id": None,
        "inviter_name": "",
        "invite_code": "",
        "invite_url": "",
        "inviter_count_at_join": 0,
        "created_at": NOW,
        "updated_at": NOW,
    },
    unique_sets=[["guild_id", "user_id"]],
    json_fields=set([]),
    datetime_fields=set(["created_at", "updated_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    inviter_id: int = None,
    inviter_name: str = None,
    invite_code: str = None,
    invite_url: str = None,
    inviter_count_at_join: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    user_id: int = None,
    inviter_id: int = None,
    inviter_name: str = None,
    invite_code: str = None,
    invite_url: str = None,
    inviter_count_at_join: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    inviter_id: int = None,
    inviter_name: str = None,
    invite_code: str = None,
    invite_url: str = None,
    inviter_count_at_join: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    inviter_id: int = None,
    inviter_name: str = None,
    invite_code: str = None,
    invite_url: str = None,
    inviter_count_at_join: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    inviter_id: int = None,
    inviter_name: str = None,
    invite_code: str = None,
    invite_url: str = None,
    inviter_count_at_join: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

