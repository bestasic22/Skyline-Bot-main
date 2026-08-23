from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "bot_plan_subscriptions"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "current_plan": "free",
        "pending_plan": "",
        "auto_renew": True,
        "status": "free",
        "last_notice": "",
        "meta": {},
        "created_at": NOW,
        "updated_at": NOW,
    },
    unique_sets=[["guild_id"]],
    json_fields=set(["meta"]),
    datetime_fields=set(
        [
            "created_at",
            "updated_at",
            "current_period_start",
            "current_period_end",
            "grace_notified_at",
            "grace_until",
            "premium_disabled_at",
            "unpaid_since",
            "purge_due_at",
            "purge_done_at",
            "last_charge_at",
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

