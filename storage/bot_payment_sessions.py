from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "bot_payment_sessions"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "mode": "topup",
        "status": "pending",
        "amount": 0.0,
        "currency": "THB",
        "provider_type": "promptpay",
        "provider_name": "",
        "verification_mode": "webhook_auto",
        "requires_manual_proof": False,
        "promptpay_number": "",
        "truemoney_phone": "",
        "bank_name": "",
        "bank_account_name": "",
        "bank_account_number": "",
        "qr_image_url": "",
        "verify_status": "pending",
        "verify_note": "",
        "transfer_reference": "",
        "transfer_link": "",
        "meta": {},
        "created_at": NOW,
        "updated_at": NOW,
    },
    unique_sets=[["session_key"]],
    json_fields=set(["meta"]),
    datetime_fields=set(
        [
            "created_at",
            "updated_at",
            "expires_at",
            "paid_at",
            "closed_at",
            "last_verified_at",
        ]
    ),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(**kwargs):
    return await _store.insert(kwargs)


async def update(id: int, **kwargs):
    return await _store.update({"id": id, **kwargs})


async def get(**kwargs):
    return await _store.get(kwargs)


async def gets(**kwargs):
    return await _store.gets(kwargs)


async def delete(**kwargs):
    return await _store.delete(kwargs)


async def get_all():
    return await _store.get_all()

