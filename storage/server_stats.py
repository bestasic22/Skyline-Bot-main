from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'server_stats'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'enabled': False,
        'stats_configs': [
            {'type': 'total_members', 'channel_id': None, 'format': '╭・สมาชิกทั้งหมด: {Count}'},
            {'type': 'members', 'channel_id': None, 'format': '┃ สมาชิก: {Count}'},
            {'type': 'bots', 'channel_id': None, 'format': '╰・บอท: {Count}'}
        ],
        'role_stats': [], # List of {'role_id': str, 'format': str, 'channel_id': str}
        'updated_at': NOW,
        'weekly_growth': [],  # List of {date: str, invites: int, members: int}
    },
    unique_sets=[['guild_id']],
    json_fields=set(['stats_configs', 'role_stats']),
    datetime_fields=set(['created_at', 'updated_at']),
    sequence_fields={},
    update_cache=('server_stats_cache', ['guild_id']),
    delete_cache=('server_stats_cache', ['guild_id']),
)

async def create_table():
    return await _store.prepare()

async def insert(**kwargs):
    return await _store.insert(kwargs)

async def update(id: int, **kwargs):
    return await _store.update({'id': id, **kwargs})

async def get(guild_id: int):
    return await _store.get({'guild_id': guild_id})

async def get_all():
    return await _store.get_all()

