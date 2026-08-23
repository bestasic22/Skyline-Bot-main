from storage.engine import CollectionStore, NOW

COLLECTION_NAME = "promote_channels"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={
        "created_at": NOW,
        "enabled": True,
        "cooldowns": {},
        "saved_messages": [],
        "allowed_domains": [],
        "allowed_urls": [],
        "blocked_words": [],
        "blocked_domains": [],
        "blocked_urls": [],
    },
    unique_sets=[["guild_id"]],
    json_fields=set(
        [
            "cooldowns",
            "saved_messages",
            "allowed_domains",
            "allowed_urls",
            "blocked_words",
            "blocked_domains",
            "blocked_urls",
        ]
    ),
    datetime_fields=set(["created_at"]),
    sequence_fields={},
    update_cache=None,
    delete_cache=None,
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    submit_channel_id: int = None,
    public_channel_id: int = None,
    enabled: bool = None,
    cooldown_seconds: int = None,
    cooldowns: dict = None,
    saved_messages: list = None,
    allowed_domains: list = None,
    allowed_urls: list = None,
    blocked_words: list = None,
    blocked_domains: list = None,
    blocked_urls: list = None,
    created_at: str = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    submit_channel_id: int = None,
    public_channel_id: int = None,
    enabled: bool = None,
    cooldown_seconds: int = None,
    cooldowns: dict = None,
    saved_messages: list = None,
    allowed_domains: list = None,
    allowed_urls: list = None,
    blocked_words: list = None,
    blocked_domains: list = None,
    blocked_urls: list = None,
    created_at: str = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    submit_channel_id: int = None,
    public_channel_id: int = None,
    enabled: bool = None,
    cooldown_seconds: int = None,
    cooldowns: dict = None,
    saved_messages: list = None,
    allowed_domains: list = None,
    allowed_urls: list = None,
    blocked_words: list = None,
    blocked_domains: list = None,
    blocked_urls: list = None,
    created_at: str = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    submit_channel_id: int = None,
    public_channel_id: int = None,
    enabled: bool = None,
    cooldown_seconds: int = None,
    cooldowns: dict = None,
    saved_messages: list = None,
    allowed_domains: list = None,
    allowed_urls: list = None,
    blocked_words: list = None,
    blocked_domains: list = None,
    blocked_urls: list = None,
    created_at: str = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    submit_channel_id: int = None,
    public_channel_id: int = None,
    enabled: bool = None,
    cooldown_seconds: int = None,
    cooldowns: dict = None,
    saved_messages: list = None,
    allowed_domains: list = None,
    allowed_urls: list = None,
    blocked_words: list = None,
    blocked_domains: list = None,
    blocked_urls: list = None,
    created_at: str = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()

