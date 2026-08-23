from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "dashboard_image_original_meta"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "created_at": NOW,
        "updated_at": NOW,
    },
    unique_sets=[["asset_id"]],
    json_fields=set(),
    datetime_fields=set(["created_at", "updated_at"]),
    sequence_fields={},
    update_cache=None,
    delete_cache=None,
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    asset_id: int = None,
    guild_id: int = None,
    original_filename: str = None,
    original_mime_type: str = None,
    original_size: int = None,
    original_width: int = None,
    original_height: int = None,
    optimized_size: int = None,
    optimized_width: int = None,
    optimized_height: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    asset_id: int = None,
    guild_id: int = None,
    original_filename: str = None,
    original_mime_type: str = None,
    original_size: int = None,
    original_width: int = None,
    original_height: int = None,
    optimized_size: int = None,
    optimized_width: int = None,
    optimized_height: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    asset_id: int = None,
    guild_id: int = None,
    original_filename: str = None,
    original_mime_type: str = None,
    original_size: int = None,
    original_width: int = None,
    original_height: int = None,
    optimized_size: int = None,
    optimized_width: int = None,
    optimized_height: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    asset_id: int = None,
    guild_id: int = None,
    original_filename: str = None,
    original_mime_type: str = None,
    original_size: int = None,
    original_width: int = None,
    original_height: int = None,
    optimized_size: int = None,
    optimized_width: int = None,
    optimized_height: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    asset_id: int = None,
    guild_id: int = None,
    original_filename: str = None,
    original_mime_type: str = None,
    original_size: int = None,
    original_width: int = None,
    original_height: int = None,
    optimized_size: int = None,
    optimized_width: int = None,
    optimized_height: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def count(
    id: int = None,
    asset_id: int = None,
    guild_id: int = None,
    original_filename: str = None,
    original_mime_type: str = None,
    original_size: int = None,
    original_width: int = None,
    original_height: int = None,
    optimized_size: int = None,
    optimized_width: int = None,
    optimized_height: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.count(locals())


async def get_all():
    return await _store.get_all()
