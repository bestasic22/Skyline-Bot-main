from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_characters"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "character_name": "",
        "character_bio": "",
        "character_job": "",
        "character_faction": "",
        "level": 1,
        "xp": 0,
        "coins": 0,
        "reputation": 0,
        "completed_scenarios": 0,
        "completed_events": 0,
        "daily_streak": 0,
        "last_daily_at": None,
        "last_story_at": None,
        "last_scenario_at": None,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id", "user_id"]],
    json_fields=set([]),
    datetime_fields=set(
        [
            "last_daily_at",
            "last_story_at",
            "last_scenario_at",
            "updated_at",
            "created_at",
        ]
    ),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    character_name: str = None,
    character_bio: str = None,
    character_job: str = None,
    character_faction: str = None,
    level: int = None,
    xp: int = None,
    coins: int = None,
    reputation: int = None,
    completed_scenarios: int = None,
    completed_events: int = None,
    daily_streak: int = None,
    last_daily_at: str = None,
    last_story_at: str = None,
    last_scenario_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    user_id: int = None,
    character_name: str = None,
    character_bio: str = None,
    character_job: str = None,
    character_faction: str = None,
    level: int = None,
    xp: int = None,
    coins: int = None,
    reputation: int = None,
    completed_scenarios: int = None,
    completed_events: int = None,
    daily_streak: int = None,
    last_daily_at: str = None,
    last_story_at: str = None,
    last_scenario_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    character_name: str = None,
    character_bio: str = None,
    character_job: str = None,
    character_faction: str = None,
    level: int = None,
    xp: int = None,
    coins: int = None,
    reputation: int = None,
    completed_scenarios: int = None,
    completed_events: int = None,
    daily_streak: int = None,
    last_daily_at: str = None,
    last_story_at: str = None,
    last_scenario_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    character_name: str = None,
    character_bio: str = None,
    character_job: str = None,
    character_faction: str = None,
    level: int = None,
    xp: int = None,
    coins: int = None,
    reputation: int = None,
    completed_scenarios: int = None,
    completed_events: int = None,
    daily_streak: int = None,
    last_daily_at: str = None,
    last_story_at: str = None,
    last_scenario_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    character_name: str = None,
    character_bio: str = None,
    character_job: str = None,
    character_faction: str = None,
    level: int = None,
    xp: int = None,
    coins: int = None,
    reputation: int = None,
    completed_scenarios: int = None,
    completed_events: int = None,
    daily_streak: int = None,
    last_daily_at: str = None,
    last_story_at: str = None,
    last_scenario_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
