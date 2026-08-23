from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'redeem_codes'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'claimed': False,
        'created_at': NOW,
        'claim_count': 0,
        'max_claims': 1,
        'lock_unique_user': False,
        'lock_unique_guild': False,
        'lock_mode': 'none',
        'used_user_ids': [],
        'used_guild_ids': [],
        'claim_history': [],
    },
    unique_sets=[['code']],
    json_fields=set(['used_user_ids', 'used_guild_ids', 'claim_history']),
    datetime_fields=set(['claimed_at', 'created_at', 'expires_at']),
    sequence_fields={},
    update_cache=('redeem_codes_cache', ['code']),
    delete_cache=('redeem_codes_cache', ['code']),
)

async def create_table():
    return await _store.prepare()

async def insert(

    id:int=None,
    code:str=None,
    code_type:str=None,
    code_value:str=None,
    valid_for_days:int=None,
    expires_at:str=None,
    claimed:bool=None,
    claimed_by:int=None,
    claimed_at:str=None,
    created_at:str=None,
    claim_count:int=None,
    max_claims:int=None,
    lock_unique_user:bool=None,
    lock_unique_guild:bool=None,
    lock_mode:str=None,
    used_user_ids:list=None,
    used_guild_ids:list=None,
    claim_history:list=None
):
    return await _store.insert(locals())

async def update(

    id:int,
    code:str=None,
    code_type:str=None,
    code_value:str=None,
    valid_for_days:int=None,
    expires_at:str=None,
    claimed:bool=None,
    claimed_by:int=None,
    claimed_at:str=None,
    created_at:str=None,
    claim_count:int=None,
    max_claims:int=None,
    lock_unique_user:bool=None,
    lock_unique_guild:bool=None,
    lock_mode:str=None,
    used_user_ids:list=None,
    used_guild_ids:list=None,
    claim_history:list=None
):
    return await _store.update(locals())

async def get(

    id:int=None,
    code:str=None,
    code_type:str=None,
    code_value:str=None,
    valid_for_days:int=None,
    expires_at:str=None,
    claimed:bool=None,
    claimed_by:int=None,
    claimed_at:str=None,
    created_at:str=None,
    claim_count:int=None,
    max_claims:int=None,
    lock_unique_user:bool=None,
    lock_unique_guild:bool=None,
    lock_mode:str=None,
    used_user_ids:list=None,
    used_guild_ids:list=None,
    claim_history:list=None
):
    return await _store.get(locals())

async def gets(

    id:int=None,
    code:str=None,
    code_type:str=None,
    code_value:str=None,
    valid_for_days:int=None,
    expires_at:str=None,
    claimed:bool=None,
    claimed_by:int=None,
    claimed_at:str=None,
    created_at:str=None,
    claim_count:int=None,
    max_claims:int=None,
    lock_unique_user:bool=None,
    lock_unique_guild:bool=None,
    lock_mode:str=None,
    used_user_ids:list=None,
    used_guild_ids:list=None,
    claim_history:list=None
):
    return await _store.gets(locals())

async def delete(

    id:int=None,
    code:str=None,
    code_type:str=None,
    code_value:str=None,
    valid_for_days:int=None,
    expires_at:str=None,
    claimed:bool=None,
    claimed_by:int=None,
    claimed_at:str=None,
    created_at:str=None,
    claim_count:int=None,
    max_claims:int=None,
    lock_unique_user:bool=None,
    lock_unique_guild:bool=None,
    lock_mode:str=None,
    used_user_ids:list=None,
    used_guild_ids:list=None,
    claim_history:list=None
):
    return await _store.delete(locals())

async def get_all():
    return await _store.get_all()


