from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'donate_settings'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'enabled': False,
        'donation_channel_id': None,
        'notification_channel_id': None,
        'reward_role_id': None,
        'color': '#6b8cff',
        'desc_discord': 'สนับสนุนพวกเราได้ง่ายๆ ผ่านระบบโดเนท!',
        'desc_web': 'สนับสนุนพวกเราเพื่อปลดล็อกฟีเจอร์ระดับพรีเมียม',
        'truemoney_phone': '',
        'promptpay_number': '',
        'bank_name': '',
        'bank_account_number': '',
        'bank_account_name': '',
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
        'goal_title': 'ค่าขนม',
        'goal_start_amount': 0,
        'goal_end_amount': 500,
        'goal_start_date': '',
        'image_url': '',
        'methods_enabled': {
            'truemoney': True,
            'promptpay': True,
            'bank': True
        },
        'updated_at': NOW,
        'created_at': NOW
    },
    unique_sets=[['guild_id']],
    json_fields=set(['methods_enabled']),
    datetime_fields=set(['created_at', 'updated_at']),
    sequence_fields={},
    update_cache=('donate_settings_cache', ['guild_id']),
    delete_cache=('donate_settings_cache', ['guild_id']),
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
