from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_permissions"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "gm_role_ids": [],
        "player_role_ids": [],
        "action_levels": {},
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id"]],
    json_fields=set(["gm_role_ids", "player_role_ids", "action_levels"]),
    datetime_fields=set(["updated_at", "created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    gm_role_ids: list = None,
    player_role_ids: list = None,
    action_levels: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    gm_role_ids: list = None,
    player_role_ids: list = None,
    action_levels: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    gm_role_ids: list = None,
    player_role_ids: list = None,
    action_levels: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    gm_role_ids: list = None,
    player_role_ids: list = None,
    action_levels: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    gm_role_ids: list = None,
    player_role_ids: list = None,
    action_levels: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
