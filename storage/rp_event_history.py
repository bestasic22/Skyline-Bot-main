from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_event_history"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "event_title": "",
        "scenario_key": "",
        "trigger_type": "manual",
        "participants_count": 0,
        "total_reward_xp": 0,
        "total_reward_coins": 0,
        "reward_xp_per_player": 0,
        "reward_coins_per_player": 0,
        "started_at": None,
        "ended_at": None,
        "created_at": NOW,
    },
    unique_sets=[],
    json_fields=set([]),
    datetime_fields=set(["started_at", "ended_at", "created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    event_title: str = None,
    scenario_key: str = None,
    trigger_type: str = None,
    participants_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    reward_xp_per_player: int = None,
    reward_coins_per_player: int = None,
    started_at: str = None,
    ended_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    event_title: str = None,
    scenario_key: str = None,
    trigger_type: str = None,
    participants_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    reward_xp_per_player: int = None,
    reward_coins_per_player: int = None,
    started_at: str = None,
    ended_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    event_title: str = None,
    scenario_key: str = None,
    trigger_type: str = None,
    participants_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    reward_xp_per_player: int = None,
    reward_coins_per_player: int = None,
    started_at: str = None,
    ended_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    event_title: str = None,
    scenario_key: str = None,
    trigger_type: str = None,
    participants_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    reward_xp_per_player: int = None,
    reward_coins_per_player: int = None,
    started_at: str = None,
    ended_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    event_title: str = None,
    scenario_key: str = None,
    trigger_type: str = None,
    participants_count: int = None,
    total_reward_xp: int = None,
    total_reward_coins: int = None,
    reward_xp_per_player: int = None,
    reward_coins_per_player: int = None,
    started_at: str = None,
    ended_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()


async def delete_limited(limit: int, filters: dict | None = None):
    return await _store.delete_limited(limit, filters or {})
