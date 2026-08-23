from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "dashboard_image_assets"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "created_at": NOW,
        "updated_at": NOW,
        "storage_backend": "gridfs",
        "gridfs_bucket": "dashboard_image_blob",
        "is_active": True,
    },
    unique_sets=[["asset_key"], ["gridfs_file_id"]],
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
    asset_key: str = None,
    guild_id: int = None,
    upload_target: str = None,
    asset_kind: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    storage_backend: str = None,
    gridfs_bucket: str = None,
    gridfs_file_id: str = None,
    mime_type: str = None,
    sha256: str = None,
    width: int = None,
    height: int = None,
    original_size: int = None,
    optimized_size: int = None,
    uploader_id: int = None,
    is_active: bool = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    asset_key: str = None,
    guild_id: int = None,
    upload_target: str = None,
    asset_kind: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    storage_backend: str = None,
    gridfs_bucket: str = None,
    gridfs_file_id: str = None,
    mime_type: str = None,
    sha256: str = None,
    width: int = None,
    height: int = None,
    original_size: int = None,
    optimized_size: int = None,
    uploader_id: int = None,
    is_active: bool = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    asset_key: str = None,
    guild_id: int = None,
    upload_target: str = None,
    asset_kind: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    storage_backend: str = None,
    gridfs_bucket: str = None,
    gridfs_file_id: str = None,
    mime_type: str = None,
    sha256: str = None,
    width: int = None,
    height: int = None,
    original_size: int = None,
    optimized_size: int = None,
    uploader_id: int = None,
    is_active: bool = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    asset_key: str = None,
    guild_id: int = None,
    upload_target: str = None,
    asset_kind: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    storage_backend: str = None,
    gridfs_bucket: str = None,
    gridfs_file_id: str = None,
    mime_type: str = None,
    sha256: str = None,
    width: int = None,
    height: int = None,
    original_size: int = None,
    optimized_size: int = None,
    uploader_id: int = None,
    is_active: bool = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    asset_key: str = None,
    guild_id: int = None,
    upload_target: str = None,
    asset_kind: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    storage_backend: str = None,
    gridfs_bucket: str = None,
    gridfs_file_id: str = None,
    mime_type: str = None,
    sha256: str = None,
    width: int = None,
    height: int = None,
    original_size: int = None,
    optimized_size: int = None,
    uploader_id: int = None,
    is_active: bool = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def count(
    id: int = None,
    asset_key: str = None,
    guild_id: int = None,
    upload_target: str = None,
    asset_kind: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    storage_backend: str = None,
    gridfs_bucket: str = None,
    gridfs_file_id: str = None,
    mime_type: str = None,
    sha256: str = None,
    width: int = None,
    height: int = None,
    original_size: int = None,
    optimized_size: int = None,
    uploader_id: int = None,
    is_active: bool = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.count(locals())


async def get_all():
    return await _store.get_all()
