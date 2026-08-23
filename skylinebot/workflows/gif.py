import requests
import random
import time

from skylinebot.config.config import urls

_GIF_CACHE_TTL_SECONDS = 300
_GIF_RESULT_CACHE: dict[tuple[str, int], tuple[float, list[dict]]] = {}


def get_gif(name:str,limit:int=10):
    base_url = urls.gif_api_base
    cache_key = (str(name or "").strip().lower(), int(limit or 10))
    now = time.monotonic()
    cached = _GIF_RESULT_CACHE.get(cache_key)
    if cached and now - cached[0] < _GIF_CACHE_TTL_SECONDS:
        results = cached[1]
        selected_gif = random.choice(results) if results else None
        if not selected_gif:
            return None
        media = selected_gif.get('media') or []
        if not media:
            return None
        return media[0].get('gif',{}).get('url',None)
    params = {
        "q":name,
        "key":urls.gif_api_key,
        "limit":limit
    }
    try:
        response = requests.get(base_url, params=params, timeout=6)
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    results = data.get('results',[])
    _GIF_RESULT_CACHE[cache_key] = (now, results)
    selected_gif = random.choice(results) if results else None
    if not selected_gif:
        return None
    media = selected_gif.get('media') or []
    if not media:
        return None
    return media[0].get('gif',{}).get('url',None)
