from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_schedules"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "schedule_name": "",
        "enabled": True,
        "frequency": "daily",
        "weekday": 0,
        "hour": 20,
        "minute": 0,
        "timezone_offset_minutes": 0,
        "duration_minutes": 30,
        "scenario_id": None,
        "scenario_key": "",
        "reward_xp_override": None,
        "reward_coins_override": None,
        "last_run_at": None,
        "next_run_at": None,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id", "schedule_name"]],
    json_fields=set([]),
    datetime_fields=set(["last_run_at", "next_run_at", "updated_at", "created_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    schedule_name: str = None,
    enabled: bool = None,
    frequency: str = None,
    weekday: int = None,
    hour: int = None,
    minute: int = None,
    timezone_offset_minutes: int = None,
    duration_minutes: int = None,
    scenario_id: int = None,
    scenario_key: str = None,
    reward_xp_override: int = None,
    reward_coins_override: int = None,
    last_run_at: str = None,
    next_run_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    schedule_name: str = None,
    enabled: bool = None,
    frequency: str = None,
    weekday: int = None,
    hour: int = None,
    minute: int = None,
    timezone_offset_minutes: int = None,
    duration_minutes: int = None,
    scenario_id: int = None,
    scenario_key: str = None,
    reward_xp_override: int = None,
    reward_coins_override: int = None,
    last_run_at: str = None,
    next_run_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    schedule_name: str = None,
    enabled: bool = None,
    frequency: str = None,
    weekday: int = None,
    hour: int = None,
    minute: int = None,
    timezone_offset_minutes: int = None,
    duration_minutes: int = None,
    scenario_id: int = None,
    scenario_key: str = None,
    reward_xp_override: int = None,
    reward_coins_override: int = None,
    last_run_at: str = None,
    next_run_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    schedule_name: str = None,
    enabled: bool = None,
    frequency: str = None,
    weekday: int = None,
    hour: int = None,
    minute: int = None,
    timezone_offset_minutes: int = None,
    duration_minutes: int = None,
    scenario_id: int = None,
    scenario_key: str = None,
    reward_xp_override: int = None,
    reward_coins_override: int = None,
    last_run_at: str = None,
    next_run_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    schedule_name: str = None,
    enabled: bool = None,
    frequency: str = None,
    weekday: int = None,
    hour: int = None,
    minute: int = None,
    timezone_offset_minutes: int = None,
    duration_minutes: int = None,
    scenario_id: int = None,
    scenario_key: str = None,
    reward_xp_override: int = None,
    reward_coins_override: int = None,
    last_run_at: str = None,
    next_run_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
