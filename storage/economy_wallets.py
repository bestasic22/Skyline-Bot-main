from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "economy_wallets"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "cash": 0,
        "bank": 0,
        "total_earned": 0,
        "total_spent": 0,
        "work_at": None,
        "slut_at": None,
        "crime_at": None,
        "rob_at": None,
        "chat_at": None,
        "collect_income_at": None,
        "collect_income_role_at": {},
        "updated_at": NOW,
        "created_at": NOW,
    },
    unique_sets=[["guild_id", "user_id"]],
    json_fields=set(["collect_income_role_at"]),
    datetime_fields=set(
        [
            "work_at",
            "slut_at",
            "crime_at",
            "rob_at",
            "chat_at",
            "collect_income_at",
            "updated_at",
            "created_at",
        ]
    ),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    cash: int = None,
    bank: int = None,
    total_earned: int = None,
    total_spent: int = None,
    work_at: str = None,
    slut_at: str = None,
    crime_at: str = None,
    rob_at: str = None,
    chat_at: str = None,
    collect_income_at: str = None,
    collect_income_role_at: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    user_id: int = None,
    cash: int = None,
    bank: int = None,
    total_earned: int = None,
    total_spent: int = None,
    work_at: str = None,
    slut_at: str = None,
    crime_at: str = None,
    rob_at: str = None,
    chat_at: str = None,
    collect_income_at: str = None,
    collect_income_role_at: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    cash: int = None,
    bank: int = None,
    total_earned: int = None,
    total_spent: int = None,
    work_at: str = None,
    slut_at: str = None,
    crime_at: str = None,
    rob_at: str = None,
    chat_at: str = None,
    collect_income_at: str = None,
    collect_income_role_at: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    cash: int = None,
    bank: int = None,
    total_earned: int = None,
    total_spent: int = None,
    work_at: str = None,
    slut_at: str = None,
    crime_at: str = None,
    rob_at: str = None,
    chat_at: str = None,
    collect_income_at: str = None,
    collect_income_role_at: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    user_id: int = None,
    cash: int = None,
    bank: int = None,
    total_earned: int = None,
    total_spent: int = None,
    work_at: str = None,
    slut_at: str = None,
    crime_at: str = None,
    rob_at: str = None,
    chat_at: str = None,
    collect_income_at: str = None,
    collect_income_role_at: dict = None,
    updated_at: str = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

