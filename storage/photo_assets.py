from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "photo_assets"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "created_at": NOW,
        "updated_at": NOW,
    },
    unique_sets=[["scope_guild_id", "slug"], ["control_message_id"]],
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
    guild_id: int = None,
    scope_guild_id: int = None,
    slug: str = None,
    display_name: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    external_url: str = None,
    external_id: str = None,
    storage_backend: str = None,
    storage_channel_id: int = None,
    storage_message_id: int = None,
    storage_guild_id: int = None,
    mime_type: str = None,
    file_size: int = None,
    uploader_id: int = None,
    upload_channel_id: int = None,
    source_message_id: int = None,
    control_message_id: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    scope_guild_id: int = None,
    slug: str = None,
    display_name: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    external_url: str = None,
    external_id: str = None,
    storage_backend: str = None,
    storage_channel_id: int = None,
    storage_message_id: int = None,
    storage_guild_id: int = None,
    mime_type: str = None,
    file_size: int = None,
    uploader_id: int = None,
    upload_channel_id: int = None,
    source_message_id: int = None,
    control_message_id: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    scope_guild_id: int = None,
    slug: str = None,
    display_name: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    external_url: str = None,
    external_id: str = None,
    storage_backend: str = None,
    storage_channel_id: int = None,
    storage_message_id: int = None,
    storage_guild_id: int = None,
    mime_type: str = None,
    file_size: int = None,
    uploader_id: int = None,
    upload_channel_id: int = None,
    source_message_id: int = None,
    control_message_id: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    scope_guild_id: int = None,
    slug: str = None,
    display_name: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    external_url: str = None,
    external_id: str = None,
    storage_backend: str = None,
    storage_channel_id: int = None,
    storage_message_id: int = None,
    storage_guild_id: int = None,
    mime_type: str = None,
    file_size: int = None,
    uploader_id: int = None,
    upload_channel_id: int = None,
    source_message_id: int = None,
    control_message_id: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    scope_guild_id: int = None,
    slug: str = None,
    display_name: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    external_url: str = None,
    external_id: str = None,
    storage_backend: str = None,
    storage_channel_id: int = None,
    storage_message_id: int = None,
    storage_guild_id: int = None,
    mime_type: str = None,
    file_size: int = None,
    uploader_id: int = None,
    upload_channel_id: int = None,
    source_message_id: int = None,
    control_message_id: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.delete(locals())


async def count(
    id: int = None,
    guild_id: int = None,
    scope_guild_id: int = None,
    slug: str = None,
    display_name: str = None,
    original_filename: str = None,
    stored_filename: str = None,
    external_url: str = None,
    external_id: str = None,
    storage_backend: str = None,
    storage_channel_id: int = None,
    storage_message_id: int = None,
    storage_guild_id: int = None,
    mime_type: str = None,
    file_size: int = None,
    uploader_id: int = None,
    upload_channel_id: int = None,
    source_message_id: int = None,
    control_message_id: int = None,
    created_at: str = None,
    updated_at: str = None,
):
    return await _store.count(locals())


async def get_all():
    return await _store.get_all()
