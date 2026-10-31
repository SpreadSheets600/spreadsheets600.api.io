import base64

from workers import fetch

DAY = 60 * 60 * 24


async def data_uri(cache, url, ttl=DAY):
    if not url:
        return None

    key = f"img:{url}"
    cached = await cache.get(key)

    if cached:
        return cached

    try:
        response = await fetch(url)

        if response.status != 200:
            return None

        body = await response.bytes()
        mime = (response.headers.get("content-type") or "image/png").split(";")[0]

    except Exception as error:
        print(f"Failed To Fetch Image {url}: {error}")
        return None

    uri = f"data:{mime};base64,{base64.b64encode(body).decode()}"
    await cache.set(key, uri, ttl)

    return uri
