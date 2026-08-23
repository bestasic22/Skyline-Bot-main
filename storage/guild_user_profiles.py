from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "guild_user_profiles"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "guild_id": None,
        "user_id": None,
        "relationship": "single",
        "spouse_id": 0,
        "married_at": None,
        "proposal_to_id": 0,
        "proposal_from_id": 0,
        "proposal_at": None,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id", "user_id"]],
    json_fields=set([]),
    datetime_fields=set(["married_at", "proposal_at", "updated_at", "created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    relationship: str = None,
    spouse_id: int = None,
    married_at: str = None,
    proposal_to_id: int = None,
    proposal_from_id: int = None,
    proposal_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    user_id: int = None,
    relationship: str = None,
    spouse_id: int = None,
    married_at: str = None,
    proposal_to_id: int = None,
    proposal_from_id: int = None,
    proposal_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    relationship: str = None,
    spouse_id: int = None,
    married_at: str = None,
    proposal_to_id: int = None,
    proposal_from_id: int = None,
    proposal_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    relationship: str = None,
    spouse_id: int = None,
    married_at: str = None,
    proposal_to_id: int = None,
    proposal_from_id: int = None,
    proposal_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    relationship: str = None,
    spouse_id: int = None,
    married_at: str = None,
    proposal_to_id: int = None,
    proposal_from_id: int = None,
    proposal_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
