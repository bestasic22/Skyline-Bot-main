from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'shop_orders'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'guild_id': None,
        'order_code': '',
        'user_id': None,
        'product_id': None,
        'product_snapshot': {},
        'quantity': 1,
        'unit_price': 0.0,
        'total_price': 0.0,
        'currency_symbol': 'THB',
        'status': 'pending_payment',
        'payment_method': 'manual',
        'payment_evidence_link': '',
        'payment_reference': '',
        'verify_status': 'pending',
        'verify_note': '',
        'reviewed_by_user_id': None,
        'delivery_status': 'pending',
        'delivery_note': '',
        'delivered_payload': '',
        'created_at': NOW,
        'updated_at': NOW,
        'paid_at': None,
        'delivered_at': None,
    },
    unique_sets=[['order_code']],
    json_fields=set(['product_snapshot']),
    datetime_fields=set(['created_at', 'updated_at', 'paid_at', 'delivered_at']),
    sequence_fields={'order_no': ['guild_id']},
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
    order_code: str = None,
):
    return await _store.get({'id': id, 'guild_id': guild_id, 'order_code': order_code})


async def gets(
    guild_id: int = None,
    user_id: int = None,
    status: str = None,
):
    return await _store.gets({'guild_id': guild_id, 'user_id': user_id, 'status': status})


async def delete(
    id: int = None,
    guild_id: int = None,
    order_code: str = None,
):
    return await _store.delete({'id': id, 'guild_id': guild_id, 'order_code': order_code})


async def get_all():
    return await _store.get_all()

