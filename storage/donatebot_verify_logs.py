from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "donatebot_verify_logs"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "source": "dashboard_donatebot_verify",
        "verify_status": "pending",
        "verify_note": "",
        "gift_link": "",
        "donor_name": "",
        "donor_discord_id": "",
        "donor_avatar_url": "",
        "donor_source": "unknown",
        "amount": 0,
        "requester_user_id": None,
        "requester_username": "",
        "requester_global_name": "",
        "requester_avatar_url": "",
        "requester_is_admin": False,
        "requester_ip": "",
        "checked_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[],
    json_fields=set([]),
    datetime_fields=set(["checked_at", "created_at"]),
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

