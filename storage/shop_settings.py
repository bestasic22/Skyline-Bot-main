from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'shop_settings'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'enabled': False,
        'currency_symbol': 'THB',
        'payment_mode': 'manual',
        'allow_wallet_payment': True,
        'auto_verify': True,
        'auto_delivery': True,
        'auto_open_ticket_on_failed_delivery': False,
        'promptpay_number': '',
        'truemoney_phone': '',
        'truemoney_gift_enabled': True,
        'shipok_enabled': False,
        'slipok_api_url': 'https://api.slipok.com/api/line/apikey/1150',
        'slipok_key': '',
        'slipcheck_verify_engine': 'slipok',
        'slipcheck_expected_receiver_name': '',
        'slipcheck_expected_receiver_first_name_th': '',
        'slipcheck_expected_receiver_last_name_th': '',
        'slipcheck_expected_receiver_first_name_en': '',
        'slipcheck_expected_receiver_last_name_en': '',
        'slipcheck_expected_receiver_bank': '',
        'slipcheck_expected_receiver_account': '',
        'slipcheck_expected_sender_name': '',
        'slipcheck_expected_sender_first_name_th': '',
        'slipcheck_expected_sender_last_name_th': '',
        'slipcheck_expected_sender_first_name_en': '',
        'slipcheck_expected_sender_last_name_en': '',
        'slipcheck_expected_sender_bank': '',
        'slipcheck_expected_sender_account': '',
        'slipcheck_expected_reference': '',
        'slipcheck_expected_qr_reference': '',
        'slipcheck_max_age_minutes': 1440,
        'slipcheck_auto_approve_confidence': 85.0,
        'slipcheck_manual_review_confidence': 55.0,
        'slipcheck_duplicate_window_hours': 72,
        'slipcheck_review_channel_id': None,
        'slipcheck_review_dm_user_ids': '',
        'support_role_ids': [],
        'buyer_view_only_roles': False,
        'shop_channel_id': None,
        'order_log_channel_id': None,
        'admin_contact_channel_id': None,
        'created_at': NOW,
        'updated_at': NOW,
    },
    unique_sets=[['guild_id']],
    json_fields=set(['support_role_ids']),
    datetime_fields=set(['created_at', 'updated_at']),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(**kwargs):
    return await _store.insert(kwargs)


async def update(id: int, **kwargs):
    return await _store.update({'id': id, **kwargs})


async def get(guild_id: int = None, id: int = None):
    return await _store.get({'guild_id': guild_id, 'id': id})


async def gets(guild_id: int = None):
    return await _store.gets({'guild_id': guild_id})


async def delete(guild_id: int = None, id: int = None):
    return await _store.delete({'guild_id': guild_id, 'id': id})


async def get_all():
    return await _store.get_all()

