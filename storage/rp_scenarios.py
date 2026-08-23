from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_scenarios"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "scenario_key": "",
        "name": "",
        "description": "",
        "template_key": "custom",
        "difficulty": "normal",
        "reward_xp": 50,
        "reward_coins": 100,
        "is_enabled": True,
        "is_preset": False,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id", "scenario_key"]],
    json_fields=set([]),
    datetime_fields=set(["updated_at", "created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    name: str = None,
    description: str = None,
    template_key: str = None,
    difficulty: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    is_enabled: bool = None,
    is_preset: bool = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    scenario_key: str = None,
    name: str = None,
    description: str = None,
    template_key: str = None,
    difficulty: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    is_enabled: bool = None,
    is_preset: bool = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    name: str = None,
    description: str = None,
    template_key: str = None,
    difficulty: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    is_enabled: bool = None,
    is_preset: bool = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    name: str = None,
    description: str = None,
    template_key: str = None,
    difficulty: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    is_enabled: bool = None,
    is_preset: bool = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    name: str = None,
    description: str = None,
    template_key: str = None,
    difficulty: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    is_enabled: bool = None,
    is_preset: bool = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
