from storage.engine import CollectionStore, NOW
from skylinebot.console.logging import logger

COLLECTION_NAME = 'automod'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={'mode': 'normal', 'antilink_enabled': False, 'antilink_whitelist_roles': [], 'antilink_whitelist_channels': [], 'antispam_enabled': False, 'antispam_whitelist_roles': [], 'antispam_whitelist_channels': [], 'antispam_max_messages': 10, 'antispam_max_interval': 30, 'antispam_max_mentions': 5, 'antispam_max_emojis': 10, 'antispam_max_caps': 50, 'antispam_punishment': 'mute', 'antispam_punishment_duration': 10, 'antibadwords_enabled': False, 'antibadwords_whitelist_roles': [], 'antibadwords_whitelist_channels': [], 'antibadwords_words': [], 'created_at': NOW},
    unique_sets=[['guild_id']],
    json_fields=set(['antibadwords_whitelist_channels', 'antibadwords_whitelist_roles', 'antibadwords_words', 'antilink_whitelist_channels', 'antilink_whitelist_roles', 'antispam_whitelist_channels', 'antispam_whitelist_roles']),
    datetime_fields=set(['created_at']),
    sequence_fields={},
    update_cache=('automod_cache', ['guild_id']),
    delete_cache=('automod_cache', ['guild_id']),
)

async def change_automod_settings_type(cache_automod_settings:dict, new_type:str):
    """Apply preset configurations for automod based on mode type."""
    new_type = new_type.lower()
    if new_type not in ['normal', 'extreme', 'custom', 'diamond']:
        return logger.warning(f"Invalid type {new_type} is chosen for automod in guild {cache_automod_settings.get('guild_id')}")
    
    guild_id = cache_automod_settings.get('guild_id')
    settings_id = cache_automod_settings.get('id')
    
    if new_type == 'custom':
        logger.info(f"Custom automod settings chosen for guild {guild_id}")
        return
    
    if new_type == 'normal':
        # Moderate defaults
        await update(
            id=settings_id,
            antilink_enabled=True,
            antispam_enabled=True,
            antibadwords_enabled=True,
            antispam_max_messages=10,
            antispam_max_interval=30,
            antispam_max_mentions=5,
            antispam_max_emojis=15,
            antispam_max_caps=60,
            antispam_punishment='mute',
            antispam_punishment_duration=10,
        )
        logger.info(f"Normal automod preset applied for guild {guild_id}")
        
    elif new_type == 'extreme':
        # Strict defaults
        await update(
            id=settings_id,
            antilink_enabled=True,
            antispam_enabled=True,
            antibadwords_enabled=True,
            antispam_max_messages=5,
            antispam_max_interval=15,
            antispam_max_mentions=3,
            antispam_max_emojis=5,
            antispam_max_caps=40,
            antispam_punishment='mute',
            antispam_punishment_duration=30,
        )
        logger.info(f"Extreme automod preset applied for guild {guild_id}")
    elif new_type == 'diamond':
        # Premium defaults
        await update(
            id=settings_id,
            antilink_enabled=True,
            antispam_enabled=True,
            antibadwords_enabled=True,
            antispam_max_messages=10,
            antispam_max_interval=30,
            antispam_max_mentions=5,
            antispam_max_emojis=10,
            antispam_max_caps=50,
            antispam_punishment='mute',
            antispam_punishment_duration=10,
            mode='custom',
        )
        logger.info(f"Diamond automod preset applied for guild {guild_id}")


async def create_table():
    return await _store.prepare()

async def insert(
    id:int=None,
    guild_id:int=None,
    mode:str=None,
    antilink_enabled:bool=None,
    antilink_rule_id:int=None,
    antilink_whitelist_roles:list=None,
    antilink_whitelist_channels:list=None,
    antispam_enabled:bool=None,
    antispam_whitelist_roles:list=None,
    antispam_whitelist_channels:list=None,
    antispam_max_messages:int=None,
    antispam_max_interval:int=None,
    antispam_max_mentions:int=None,
    antispam_max_emojis:int=None,
    antispam_max_caps:int=None,
    antispam_punishment:str=None,
    antispam_punishment_duration:int=None,
    antibadwords_enabled:bool=None,
    antibadwords_rule_id:int=None,
    antibadwords_whitelist_roles:list=None,
    antibadwords_whitelist_channels:list=None,
    antibadwords_words:list=None,
    created_at:str=None
):
    return await _store.insert(locals())

async def update(
    id:int,
    guild_id:int=None,
    mode:str=None,
    antilink_enabled:bool=None,
    antilink_rule_id:int=None,
    antilink_whitelist_roles:list=None,
    antilink_whitelist_channels:list=None,
    antispam_enabled:bool=None,
    antispam_whitelist_roles:list=None,
    antispam_whitelist_channels:list=None,
    antispam_max_messages:int=None,
    antispam_max_interval:int=None,
    antispam_max_mentions:int=None,
    antispam_max_emojis:int=None,
    antispam_max_caps:int=None,
    antispam_punishment:str=None,
    antispam_punishment_duration:int=None,
    antibadwords_enabled:bool=None,
    antibadwords_rule_id:int=None,
    antibadwords_whitelist_roles:list=None,
    antibadwords_whitelist_channels:list=None,
    antibadwords_words:list=None,
    created_at:str=None
):
    return await _store.update(locals())

async def get(
    id:int=None,
    guild_id:int=None,
    mode:str=None,
    antilink_enabled:bool=None,
    antilink_rule_id:int=None,
    antilink_whitelist_roles:list=None,
    antilink_whitelist_channels:list=None,
    antispam_enabled:bool=None,
    antispam_whitelist_roles:list=None,
    antispam_whitelist_channels:list=None,
    antispam_max_messages:int=None,
    antispam_max_interval:int=None,
    antispam_max_mentions:int=None,
    antispam_max_emojis:int=None,
    antispam_max_caps:int=None,
    antispam_punishment:str=None,
    antispam_punishment_duration:int=None,
    antibadwords_enabled:bool=None,
    antibadwords_rule_id:int=None,
    antibadwords_whitelist_roles:list=None,
    antibadwords_whitelist_channels:list=None,
    antibadwords_words:list=None,
    created_at:str=None
):
    return await _store.get(locals())

async def gets(
    id:int=None,
    guild_id:int=None,
    mode:str=None,
    antilink_enabled:bool=None,
    antilink_rule_id:int=None,
    antilink_whitelist_roles:list=None,
    antilink_whitelist_channels:list=None,
    antispam_enabled:bool=None,
    antispam_whitelist_roles:list=None,
    antispam_whitelist_channels:list=None,
    antispam_max_messages:int=None,
    antispam_max_interval:int=None,
    antispam_max_mentions:int=None,
    antispam_max_emojis:int=None,
    antispam_max_caps:int=None,
    antispam_punishment:str=None,
    antispam_punishment_duration:int=None,
    antibadwords_enabled:bool=None,
    antibadwords_rule_id:int=None,
    antibadwords_whitelist_roles:list=None,
    antibadwords_whitelist_channels:list=None,
    antibadwords_words:list=None,
    created_at:str=None
):
    return await _store.gets(locals())

async def delete(

    id:int=None,
    guild_id:int=None,
    antilink_enabled:bool=None,
    antilink_rule_id:int=None,
    antilink_whitelist_roles:list=None,
    antilink_whitelist_channels:list=None,
    antispam_enabled:bool=None,
    antispam_whitelist_roles:list=None,
    antispam_whitelist_channels:list=None,
    antispam_max_messages:int=None,
    antispam_max_interval:int=None,
    antispam_max_mentions:int=None,
    antispam_max_emojis:int=None,
    antispam_max_caps:int=None,
    antispam_punishment:str=None,
    antispam_punishment_duration:int=None,
    antibadwords_enabled:bool=None,
    antibadwords_rule_id:int=None,
    antibadwords_whitelist_roles:list=None,
    antibadwords_whitelist_channels:list=None,
    antibadwords_words:list=None,
    created_at:str=None
):
    return await _store.delete(locals())

async def get_all():
    return await _store.get_all()

