from skylinebot.workflows.cache import load_cache
from skylinebot.workflows.storage_sync import load_storage


async def prepare_runtime():
    await load_storage()
    await load_cache()

