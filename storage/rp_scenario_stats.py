from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_scenario_stats"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "scenario_key": "",
        "scenario_name": "",
        "play_count": 0,
        "event_start_count": 0,
        "total_reward_xp": 0,
        "total_reward_coins": 0,
        "last_played_at": None,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id", "scenario_key"]],
    json_fields=set([]),
    datetime_fields=set(["last_played_at", "updated_at", "created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    scenario_name: str = None,
    play_count: int = None,
    event_start_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    last_played_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    scenario_key: str = None,
    scenario_name: str = None,
    play_count: int = None,
    event_start_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    last_played_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    scenario_name: str = None,
    play_count: int = None,
    event_start_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    last_played_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    scenario_name: str = None,
    play_count: int = None,
    event_start_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    last_played_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    scenario_key: str = None,
    scenario_name: str = None,
    play_count: int = None,
    event_start_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    last_played_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
