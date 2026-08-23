from storage.engine import CollectionStore, NOW

COLLECTION_NAME = 'image_ocr_settings'
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        'enabled': False,
        'target_channel_id': None,
        'admin_channel_id': None,
        'notification_channel_id': None,
        'webhook_url': None,
        'notify_embed_title': 'ตรวจพบข้อความจากรูปภาพ',
        'notify_embed_description': 'พบคีย์เวิร์ด: {keywords}\nผู้ใช้: {user_mention}\nจำนวนรูปสะสม: {current_count}/{required_count}',
        'notify_embed_image_url': None,
        'required_image_count': 1,
        'reward_role_id': None,
        'keywords': ["Following", "Shared", "Subscribed"],
        'confidence_threshold': 80,
        'updated_at': NOW,
        'created_at': NOW,
    },
    unique_sets=[['guild_id']],
    json_fields=set(['keywords']),
    datetime_fields=set(['created_at', 'updated_at']),
    sequence_fields={},
    update_cache=('image_ocr_cache', ['guild_id']),
    delete_cache=('image_ocr_cache', ['guild_id']),
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    enabled: bool = None,
    target_channel_id: str = None,
    admin_channel_id: str = None,
    notification_channel_id: str = None,
    webhook_url: str = None,
    notify_embed_title: str = None,
    notify_embed_description: str = None,
    notify_embed_image_url: str = None,
    required_image_count: int = None,
    image_count: int = None,
    reward_role_id: str = None,
    keywords: list = None,
    confidence_threshold: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    # Alias: image_count maps to required_image_count
    if image_count is not None and required_image_count is None:
        required_image_count = image_count
    # Build dict excluding alias field
    data = {k: v for k, v in locals().items() if k != 'image_count' and v is not None}
    return await _store.insert(data)


async def update(
    id: int,
    guild_id: int = None,
    enabled: bool = None,
    target_channel_id: str = None,
    admin_channel_id: str = None,
    notification_channel_id: str = None,
    webhook_url: str = None,
    notify_embed_title: str = None,
    notify_embed_description: str = None,
    notify_embed_image_url: str = None,
    required_image_count: int = None,
    image_count: int = None,
    reward_role_id: str = None,
    keywords: list = None,
    confidence_threshold: int = None,
    updated_at: str = None,
    created_at: str = None,
):
    # Alias: image_count maps to required_image_count
    if image_count is not None and required_image_count is None:
        required_image_count = image_count
    # Build dict excluding alias field
    data = {k: v for k, v in locals().items() if k != 'image_count' and v is not None}
    return await _store.update(data)


async def get(guild_id: int):
    data = await _store.get({'guild_id': guild_id})
    if data and 'required_image_count' in data and 'image_count' not in data:
        data['image_count'] = data['required_image_count']
    return data


async def get_all():
    return await _store.get_all()

