from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_economy_guard"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "enabled": False,
        "max_reward_xp": 250000,
        "max_reward_coins": 250000,
        "inflation_threshold_avg_coins": 25000,
        "base_reduce_percent": 20,
        "min_multiplier_percent": 55,
        "last_multiplier_percent": 100,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id"]],
    json_fields=set([]),
    datetime_fields=set(["updated_at", "created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    max_reward_xp: int = None,
    max_reward_coins: int = None,
    inflation_threshold_avg_coins: int = None,
    base_reduce_percent: int = None,
    min_multiplier_percent: int = None,
    last_multiplier_percent: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    enabled: bool = None,
    max_reward_xp: int = None,
    max_reward_coins: int = None,
    inflation_threshold_avg_coins: int = None,
    base_reduce_percent: int = None,
    min_multiplier_percent: int = None,
    last_multiplier_percent: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    max_reward_xp: int = None,
    max_reward_coins: int = None,
    inflation_threshold_avg_coins: int = None,
    base_reduce_percent: int = None,
    min_multiplier_percent: int = None,
    last_multiplier_percent: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    max_reward_xp: int = None,
    max_reward_coins: int = None,
    inflation_threshold_avg_coins: int = None,
    base_reduce_percent: int = None,
    min_multiplier_percent: int = None,
    last_multiplier_percent: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    max_reward_xp: int = None,
    max_reward_coins: int = None,
    inflation_threshold_avg_coins: int = None,
    base_reduce_percent: int = None,
    min_multiplier_percent: int = None,
    last_multiplier_percent: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
