from storage.engine import CollectionStore

COLLECTION_NAME = "fun_rooms"
CollectionName = COLLECTION_NAME

_store = CollectionStore(
    name=COLLECTION_NAME,
    defaults={},
    unique_sets=[["guild_id"]],
    json_fields=set([]),
    datetime_fields=set([]),
    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id: int = None,
    guild_id: int = None,
    counting_up_channel_id: int = None,
    counting_down_channel_id: int = None,
    word_twist_channel_id: int = None,
    guess_word_channel_id: int = None,
    xo_channel_id: int = None,
    chess_channel_id: int = None,
    slots_channel_id: int = None,
    rps_channel_id: int = None,
    dice_channel_id: int = None,
    coinflip_channel_id: int = None,
    number_guess_channel_id: int = None,
    word_chain_channel_id: int = None,
    quiz_channel_id: int = None,
):
    return await _store.insert(locals())


async def update(
    id: int,
    guild_id: int = None,
    counting_up_channel_id: int = None,
    counting_down_channel_id: int = None,
    word_twist_channel_id: int = None,
    guess_word_channel_id: int = None,
    xo_channel_id: int = None,
    chess_channel_id: int = None,
    slots_channel_id: int = None,
    rps_channel_id: int = None,
    dice_channel_id: int = None,
    coinflip_channel_id: int = None,
    number_guess_channel_id: int = None,
    word_chain_channel_id: int = None,
    quiz_channel_id: int = None,
):
    return await _store.update(locals())


async def get(
    id: int = None,
    guild_id: int = None,
    counting_up_channel_id: int = None,
    counting_down_channel_id: int = None,
    word_twist_channel_id: int = None,
    guess_word_channel_id: int = None,
    xo_channel_id: int = None,
    chess_channel_id: int = None,
    slots_channel_id: int = None,
    rps_channel_id: int = None,
    dice_channel_id: int = None,
    coinflip_channel_id: int = None,
    number_guess_channel_id: int = None,
    word_chain_channel_id: int = None,
    quiz_channel_id: int = None,
):
    return await _store.get(locals())


async def gets(
    id: int = None,
    guild_id: int = None,
    counting_up_channel_id: int = None,
    counting_down_channel_id: int = None,
    word_twist_channel_id: int = None,
    guess_word_channel_id: int = None,
    xo_channel_id: int = None,
    chess_channel_id: int = None,
    slots_channel_id: int = None,
    rps_channel_id: int = None,
    dice_channel_id: int = None,
    coinflip_channel_id: int = None,
    number_guess_channel_id: int = None,
    word_chain_channel_id: int = None,
    quiz_channel_id: int = None,
):
    return await _store.gets(locals())


async def delete(
    id: int = None,
    guild_id: int = None,
    counting_up_channel_id: int = None,
    counting_down_channel_id: int = None,
    word_twist_channel_id: int = None,
    guess_word_channel_id: int = None,
    xo_channel_id: int = None,
    chess_channel_id: int = None,
    slots_channel_id: int = None,
    rps_channel_id: int = None,
    dice_channel_id: int = None,
    coinflip_channel_id: int = None,
    number_guess_channel_id: int = None,
    word_chain_channel_id: int = None,
    quiz_channel_id: int = None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()


async def count(
    id: int = None,
    guild_id: int = None,
    counting_up_channel_id: int = None,
    counting_down_channel_id: int = None,
    word_twist_channel_id: int = None,
    guess_word_channel_id: int = None,
    xo_channel_id: int = None,
    chess_channel_id: int = None,
    slots_channel_id: int = None,
    rps_channel_id: int = None,
    dice_channel_id: int = None,
    coinflip_channel_id: int = None,
    number_guess_channel_id: int = None,
    word_chain_channel_id: int = None,
    quiz_channel_id: int = None,
):
    return await _store.count(locals())

