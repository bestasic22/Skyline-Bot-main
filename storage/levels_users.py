from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "levels_users"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "guild_id": None,
        "user_id": None,
        "level": 0,
        "total_xp": 0,
        "text_xp": 0,
        "voice_xp": 0,
        "command_xp": 0,
        "reaction_xp": 0,
        "last_text_at": None,
        "last_voice_at": None,
        "last_command_at": None,
        "last_reaction_at": None,
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id", "user_id"]],
    json_fields=set([]),
    datetime_fields=set(
        [
            "last_text_at",
            "last_voice_at",
            "last_command_at",
            "last_reaction_at",
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
    level: int = None,
    total_xp: int = None,
    text_xp: int = None,
    voice_xp: int = None,
    command_xp: int = None,
    reaction_xp: int = None,
    last_text_at: str = None,
    last_voice_at: str = None,
    last_command_at: str = None,
    last_reaction_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    user_id: int = None,
    level: int = None,
    total_xp: int = None,
    text_xp: int = None,
    voice_xp: int = None,
    command_xp: int = None,
    reaction_xp: int = None,
    last_text_at: str = None,
    last_voice_at: str = None,
    last_command_at: str = None,
    last_reaction_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    level: int = None,
    total_xp: int = None,
    text_xp: int = None,
    voice_xp: int = None,
    command_xp: int = None,
    reaction_xp: int = None,
    last_text_at: str = None,
    last_voice_at: str = None,
    last_command_at: str = None,
    last_reaction_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    level: int = None,
    total_xp: int = None,
    text_xp: int = None,
    voice_xp: int = None,
    command_xp: int = None,
    reaction_xp: int = None,
    last_text_at: str = None,
    last_voice_at: str = None,
    last_command_at: str = None,
    last_reaction_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    level: int = None,
    total_xp: int = None,
    text_xp: int = None,
    voice_xp: int = None,
    command_xp: int = None,
    reaction_xp: int = None,
    last_text_at: str = None,
    last_voice_at: str = None,
    last_command_at: str = None,
    last_reaction_at: str = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

