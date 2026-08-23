from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'music'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'default_volume': 80,
        'default_repeat': False,
        'default_autoplay': False,
        'music_usage_enabled': True,
        'music_usage_admin_only': False,
        'music_usage_restrict_enabled': False,
        'music_usage_allow_admin_bypass': True,
        'music_usage_role_ids': [],
        'music_usage_user_ids': [],
        'music_usage_channel_ids': [],
        'created_at': NOW,
    },
    unique_sets=[['guild_id']],
    json_fields={
        'music_usage_role_ids',
        'music_usage_user_ids',
        'music_usage_channel_ids',
    },
    datetime_fields=set(['created_at']),
    sequence_fields={},
    update_cache=('music_cache', ['guild_id']),
    delete_cache=('music_cache', ['guild_id']),
)

async def create_table():
    return await _store.prepare()

async def insert(

    id:int=None,
    guild_id:int=None,
    music_setup_channel_id:int=None,
    music_setup_voice_channel_id:int=None,
    music_setup_message_id:int=None,
    default_volume:int=None,
    default_repeat:bool=None,
    default_autoplay:bool=None,
    music_usage_enabled:bool=None,
    music_usage_admin_only:bool=None,
    music_usage_restrict_enabled:bool=None,
    music_usage_allow_admin_bypass:bool=None,
    music_usage_role_ids:list=None,
    music_usage_user_ids:list=None,
    music_usage_channel_ids:list=None,
    created_at:str=None
):
    return await _store.insert(locals())

async def update(

    id:int,
    guild_id:int=None,
    music_setup_channel_id:int=None,
    music_setup_voice_channel_id:int=None,
    music_setup_message_id:int=None,
    default_volume:int=None,
    default_repeat:bool=None,
    default_autoplay:bool=None,
    music_command_channel_id:int=None,
    music_voice_channel_id:int=None,
    setup_music_mode:bool=None,
    music_usage_enabled:bool=None,
    music_usage_admin_only:bool=None,
    music_usage_restrict_enabled:bool=None,
    music_usage_allow_admin_bypass:bool=None,
    music_usage_role_ids:list=None,
    music_usage_user_ids:list=None,
    music_usage_channel_ids:list=None,
    created_at:str=None
):
    if music_setup_channel_id is None and music_command_channel_id is not None:
        music_setup_channel_id = music_command_channel_id
    if music_setup_voice_channel_id is None and music_voice_channel_id is not None:
        music_setup_voice_channel_id = music_voice_channel_id

    payload = {
        'id': id,
        'guild_id': guild_id,
        'music_setup_channel_id': music_setup_channel_id,
        'music_setup_voice_channel_id': music_setup_voice_channel_id,
        'music_setup_message_id': music_setup_message_id,
        'default_volume': default_volume,
        'default_repeat': default_repeat,
        'default_autoplay': default_autoplay,
        'setup_music_mode': setup_music_mode,
        'music_usage_enabled': music_usage_enabled,
        'music_usage_admin_only': music_usage_admin_only,
        'music_usage_restrict_enabled': music_usage_restrict_enabled,
        'music_usage_allow_admin_bypass': music_usage_allow_admin_bypass,
        'music_usage_role_ids': music_usage_role_ids,
        'music_usage_user_ids': music_usage_user_ids,
        'music_usage_channel_ids': music_usage_channel_ids,
        'created_at': created_at,
    }
    return await _store.update(payload)

async def get(

    id:int=None,
    guild_id:int=None,
    music_setup_channel_id:int=None,
    music_setup_voice_channel_id:int=None,
    music_setup_message_id:int=None,
    default_volume:int=None,
    default_repeat:bool=None,
    default_autoplay:bool=None,
    music_usage_enabled:bool=None,
    music_usage_admin_only:bool=None,
    music_usage_restrict_enabled:bool=None,
    music_usage_allow_admin_bypass:bool=None,
    music_usage_role_ids:list=None,
    music_usage_user_ids:list=None,
    music_usage_channel_ids:list=None,
    created_at:str=None
):
    return await _store.get(locals())

async def gets(

    id:int=None,
    guild_id:int=None,
    music_setup_channel_id:int=None,
    music_setup_voice_channel_id:int=None,
    music_setup_message_id:int=None,
    default_volume:int=None,
    default_repeat:bool=None,
    default_autoplay:bool=None,
    music_usage_enabled:bool=None,
    music_usage_admin_only:bool=None,
    music_usage_restrict_enabled:bool=None,
    music_usage_allow_admin_bypass:bool=None,
    music_usage_role_ids:list=None,
    music_usage_user_ids:list=None,
    music_usage_channel_ids:list=None,
    created_at:str=None
):
    return await _store.gets(locals())

async def delete(

    id:int=None,
    guild_id:int=None,
    music_setup_channel_id:int=None,
    music_setup_voice_channel_id:int=None,
    music_setup_message_id:int=None,
    default_volume:int=None,
    default_repeat:bool=None,
    default_autoplay:bool=None,
    music_usage_enabled:bool=None,
    music_usage_admin_only:bool=None,
    music_usage_restrict_enabled:bool=None,
    music_usage_allow_admin_bypass:bool=None,
    music_usage_role_ids:list=None,
    music_usage_user_ids:list=None,
    music_usage_channel_ids:list=None,
    created_at:str=None
):
    return await _store.delete(locals())

async def get_all():
    return await _store.get_all()

async def count(

    id:int=None,
    guild_id:int=None,
    music_setup_channel_id:int=None,
    music_setup_voice_channel_id:int=None,
    music_setup_message_id:int=None,
    default_volume:int=None,
    default_repeat:bool=None,
    default_autoplay:bool=None,
    music_usage_enabled:bool=None,
    music_usage_admin_only:bool=None,
    music_usage_restrict_enabled:bool=None,
    music_usage_allow_admin_bypass:bool=None,
    music_usage_role_ids:list=None,
    music_usage_user_ids:list=None,
    music_usage_channel_ids:list=None,
    created_at:str=None
):
    return await _store.count(locals())

