from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'shop_products'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'guild_id': None,
        'sku': '',
        'name': 'Unnamed Product',
        'description': '',
        'price': 0.0,
        'stock': 0,
        'image_url': '',
        'enabled': True,
        'visible_role_ids': [],
        'buy_role_ids': [],
        'delivery_type': 'none',
        'delivery_role_id': None,
        'delivery_payload': '',
        'delivery_note': '',
        'sort_order': 0,
        'created_at': NOW,
        'updated_at': NOW,
    },
    unique_sets=[['guild_id', 'sku']],
    json_fields=set(['visible_role_ids', 'buy_role_ids']),
    datetime_fields=set(['created_at', 'updated_at']),
    sequence_fields={'product_no': ['guild_id']},
)


async def create_table():
    return await _store.prepare()


async def insert(**kwargs):
    return await _store.insert(kwargs)


async def update(id: int, **kwargs):
    return await _store.update({'id': id, **kwargs})


async def get(
    id: int = None,
    guild_id: int = None,
    sku: str = None,
):
    return await _store.get({'id': id, 'guild_id': guild_id, 'sku': sku})


async def gets(
    guild_id: int = None,
    enabled: bool = None,
):
    return await _store.gets({'guild_id': guild_id, 'enabled': enabled})


async def delete(
    id: int = None,
    guild_id: int = None,
    sku: str = None,
):
    return await _store.delete({'id': id, 'guild_id': guild_id, 'sku': sku})


async def get_all():
    return await _store.get_all()


async def count(
    guild_id: int = None,
    enabled: bool = None,
):
    return await _store.count({'guild_id': guild_id, 'enabled': enabled})

