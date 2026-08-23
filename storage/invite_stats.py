from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "invite_stats"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "guild_id": None,
        "inviter_id": None,
        "invite_count": 0,
        "last_invited_user_id": None,
        "last_invite_code": "",
        "last_invite_url": "",
        "last_joined_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    },
    unique_sets=[["guild_id", "inviter_id"]],
    json_fields=set([]),
    datetime_fields=set(["last_joined_at", "created_at", "updated_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    inviter_id: int = None,
    invite_count: int = None,
    last_invited_user_id: int = None,
    last_invite_code: str = None,
    last_invite_url: str = None,
    last_joined_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    inviter_id: int = None,
    invite_count: int = None,
    last_invited_user_id: int = None,
    last_invite_code: str = None,
    last_invite_url: str = None,
    last_joined_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    inviter_id: int = None,
    invite_count: int = None,
    last_invited_user_id: int = None,
    last_invite_code: str = None,
    last_invite_url: str = None,
    last_joined_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    inviter_id: int = None,
    invite_count: int = None,
    last_invited_user_id: int = None,
    last_invite_code: str = None,
    last_invite_url: str = None,
    last_joined_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    inviter_id: int = None,
    invite_count: int = None,
    last_invited_user_id: int = None,
    last_invite_code: str = None,
    last_invite_url: str = None,
    last_joined_at: str = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

