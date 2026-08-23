from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "rp_events"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "status": "idle",
        "event_title": "",
        "template_key": "",
        "description": "",
        "reward_xp": 0,
        "reward_coins": 0,
        "participants": [],
        "started_by": 0,
        "trigger_type": "manual",
        "schedule_name": "",
        "started_at": NOW,
        "ends_at": None,
        "updated_at": NOW,
    },
    unique_sets=[["guild_id"]],
    json_fields=set(["participants"]),
    datetime_fields=set(["started_at", "ends_at", "updated_at"]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    status: str = None,
    event_title: str = None,
    template_key: str = None,
    description: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    participants: list = None,
    started_by: int = None,
    trigger_type: str = None,
    schedule_name: str = None,
    started_at: str = None,
    ends_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    status: str = None,
    event_title: str = None,
    template_key: str = None,
    description: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    participants: list = None,
    started_by: int = None,
    trigger_type: str = None,
    schedule_name: str = None,
    started_at: str = None,
    ends_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    status: str = None,
    event_title: str = None,
    template_key: str = None,
    description: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    participants: list = None,
    started_by: int = None,
    trigger_type: str = None,
    schedule_name: str = None,
    started_at: str = None,
    ends_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    status: str = None,
    event_title: str = None,
    template_key: str = None,
    description: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    participants: list = None,
    started_by: int = None,
    trigger_type: str = None,
    schedule_name: str = None,
    started_at: str = None,
    ends_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    status: str = None,
    event_title: str = None,
    template_key: str = None,
    description: str = None,
    reward_xp: int = None,
    reward_coins: int = None,
    participants: list = None,
    started_by: int = None,
    trigger_type: str = None,
    schedule_name: str = None,
    started_at: str = None,
    ends_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
