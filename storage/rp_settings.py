from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_settings"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "enabled": False,
        "preset_key": "modern_city",
        "allow_custom_config": True,
        "allow_custom_scenarios": True,
        "currency_symbol": "coin",
        "start_coins": 250,
        "start_xp": 0,
        "xp_per_level": 120,
        "daily_reward_min": 80,
        "daily_reward_max": 180,
        "story_min_length": 20,
        "story_cooldown_seconds": 300,
        "story_reward_min": 12,
        "story_reward_max": 40,
        "scenario_cooldown_seconds": 900,
        "event_reward_xp": 120,
        "event_reward_coins": 220,
        "event_announce_channel_id": None,
        "schedule_notify_on_start": True,
        "schedule_notify_on_end": True,
        "max_custom_scenarios": 30,
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
    preset_key: str = None,
    allow_custom_config: bool = None,
    allow_custom_scenarios: bool = None,
    currency_symbol: str = None,
    start_coins: int = None,
    start_xp: int = None,
    xp_per_level: int = None,
    daily_reward_min: int = None,
    daily_reward_max: int = None,
    story_min_length: int = None,
    story_cooldown_seconds: int = None,
    story_reward_min: int = None,
    story_reward_max: int = None,
    scenario_cooldown_seconds: int = None,
    event_reward_xp: int = None,
    event_reward_coins: int = None,
    event_announce_channel_id: str = None,
    schedule_notify_on_start: bool = None,
    schedule_notify_on_end: bool = None,
    max_custom_scenarios: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    enabled: bool = None,
    preset_key: str = None,
    allow_custom_config: bool = None,
    allow_custom_scenarios: bool = None,
    currency_symbol: str = None,
    start_coins: int = None,
    start_xp: int = None,
    xp_per_level: int = None,
    daily_reward_min: int = None,
    daily_reward_max: int = None,
    story_min_length: int = None,
    story_cooldown_seconds: int = None,
    story_reward_min: int = None,
    story_reward_max: int = None,
    scenario_cooldown_seconds: int = None,
    event_reward_xp: int = None,
    event_reward_coins: int = None,
    event_announce_channel_id: str = None,
    schedule_notify_on_start: bool = None,
    schedule_notify_on_end: bool = None,
    max_custom_scenarios: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    preset_key: str = None,
    allow_custom_config: bool = None,
    allow_custom_scenarios: bool = None,
    currency_symbol: str = None,
    start_coins: int = None,
    start_xp: int = None,
    xp_per_level: int = None,
    daily_reward_min: int = None,
    daily_reward_max: int = None,
    story_min_length: int = None,
    story_cooldown_seconds: int = None,
    story_reward_min: int = None,
    story_reward_max: int = None,
    scenario_cooldown_seconds: int = None,
    event_reward_xp: int = None,
    event_reward_coins: int = None,
    event_announce_channel_id: str = None,
    schedule_notify_on_start: bool = None,
    schedule_notify_on_end: bool = None,
    max_custom_scenarios: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    preset_key: str = None,
    allow_custom_config: bool = None,
    allow_custom_scenarios: bool = None,
    currency_symbol: str = None,
    start_coins: int = None,
    start_xp: int = None,
    xp_per_level: int = None,
    daily_reward_min: int = None,
    daily_reward_max: int = None,
    story_min_length: int = None,
    story_cooldown_seconds: int = None,
    story_reward_min: int = None,
    story_reward_max: int = None,
    scenario_cooldown_seconds: int = None,
    event_reward_xp: int = None,
    event_reward_coins: int = None,
    event_announce_channel_id: str = None,
    schedule_notify_on_start: bool = None,
    schedule_notify_on_end: bool = None,
    max_custom_scenarios: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    preset_key: str = None,
    allow_custom_config: bool = None,
    allow_custom_scenarios: bool = None,
    currency_symbol: str = None,
    start_coins: int = None,
    start_xp: int = None,
    xp_per_level: int = None,
    daily_reward_min: int = None,
    daily_reward_max: int = None,
    story_min_length: int = None,
    story_cooldown_seconds: int = None,
    story_reward_min: int = None,
    story_reward_max: int = None,
    scenario_cooldown_seconds: int = None,
    event_reward_xp: int = None,
    event_reward_coins: int = None,
    event_announce_channel_id: str = None,
    schedule_notify_on_start: bool = None,
    schedule_notify_on_end: bool = None,
    max_custom_scenarios: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
