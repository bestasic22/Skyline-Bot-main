from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'guilds'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={'prefix': '!'},
    unique_sets=[],
    json_fields=set([]),
    datetime_fields=set([]),
    sequence_fields={},
    update_cache=('guilds_cache', ['guild_id']),
    delete_cache=('guilds_cache', ['guild_id']),
)

async def create_table():
    return await _store.prepare()

async def insert(

    id:int=None,
    guild_id:int=None,
    owner_id:int=None,
    extra_owner_ids:list=None,
    prefix:str=None,
    subscription:str=None,
    subscription_end:str=None,
    language:str=None,
    trusted_server_order:str=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.insert(locals())

async def update(

    id:int,
    guild_id:int=None,
    owner_id:int=None,
    extra_owner_ids:list=None,
    prefix:str=None,
    subscription:str=None,
    subscription_end:str=None,
    language:str=None,
    trusted_server_order:str=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.update(locals())

async def get(

    id:int=None,
    guild_id:int=None,
    owner_id:int=None,
    extra_owner_ids:list=None,
    prefix:str=None,
    subscription:str=None,
    subscription_end:str=None,
    language:str=None,
    trusted_server_order:str=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.get(locals())

async def gets(

    id:int=None,
    guild_id:int=None,
    owner_id:int=None,
    extra_owner_ids:list=None,
    prefix:str=None,
    subscription:str=None,
    subscription_end:str=None,
    language:str=None,
    trusted_server_order:str=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.gets(locals())

async def delete(

    id:int=None,
    guild_id:int=None,
    owner_id:int=None,
    extra_owner_ids:list=None,
    prefix:str=None,
    subscription:str=None,
    subscription_end:str=None,
    language:str=None,
    trusted_server_order:str=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.delete(locals())

async def get_all():
    return await _store.get_all()


