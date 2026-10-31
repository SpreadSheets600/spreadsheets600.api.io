import base64
from urllib.parse import urlencode

from workers import fetch

TOKEN_URL = "https://accounts.spotify.com/api/token"
NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
RECENT_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=1"

REFRESH_TOKEN_KEY = "spotify:refresh_token"
ACCESS_TOKEN_KEY = "spotify:access_token"
LAST_TRACK_KEY = "spotify:last_track"


async def _access_token(config, cache):
    if not (
        config.spotify_client_id
        and config.spotify_client_secret
        and config.spotify_refresh_token
    ):
        return None

    refresh_token = await cache.get(REFRESH_TOKEN_KEY) or config.spotify_refresh_token
    basic = base64.b64encode(
        f"{config.spotify_client_id}:{config.spotify_client_secret}".encode()
    ).decode()

    response = await fetch(
        TOKEN_URL,
        method="POST",
        headers={
            "authorization": f"Basic {basic}",
            "content-type": "application/x-www-form-urlencoded",
        },
        body=urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        ),
    )

    if response.status != 200:
        raise RuntimeError(f"spotify token returned {response.status}")

    data = await response.json()
    rotated = data.get("refresh_token")

    if rotated and rotated != refresh_token:
        await cache.set(REFRESH_TOKEN_KEY, rotated, 60 * 60 * 24 * 365)

    return data.get("access_token")


async def fetch_stats(config, cache):
    token = await _access_token(config, cache)

    if not token:
        return None

    response = await fetch(
        NOW_PLAYING_URL,
        headers={"authorization": f"Bearer {token}"},
    )

    if response.status == 204:
        return {"playing": False}

    if response.status != 200:
        raise RuntimeError(f"spotify now-playing returned {response.status}")

    data = await response.json()
    item = data.get("item")

    if not item:
        return {"playing": False}

    album = item.get("album") or {}
    images = album.get("images") or [{}]

    return {
        "playing": bool(data.get("is_playing")),
        "title": item.get("name"),
        "artists": ", ".join(
            artist.get("name", "") for artist in item.get("artists") or []
        ),
        "album": album.get("name"),
        "url": (item.get("external_urls") or {}).get("spotify"),
        "image": images[0].get("url"),
        "progress": data.get("progress_ms"),
        "duration": item.get("duration_ms"),
    }


async def fetch_snapshot(config, cache):
    stats = await fetch_stats(config, cache)

    if stats is None:
        return None

    return {**stats, "lastPlayed": await fetch_last_played(config, cache)}


async def _token(config, cache):
    cached = await cache.get(ACCESS_TOKEN_KEY)

    if cached:
        return cached

    token = await _access_token(config, cache)

    if token:
        await cache.set(ACCESS_TOKEN_KEY, token, 60 * 55)

    return token


def _track(item):
    album = item.get("album") or {}
    images = album.get("images") or []
    image = images[1] if len(images) > 1 else (images[0] if images else {})
    show = item.get("show") or {}

    return {
        "id": item.get("id"),
        "title": item.get("name"),
        "artists": ", ".join(
            artist.get("name", "") for artist in item.get("artists") or []
        )
        or show.get("publisher"),
        "album": album.get("name") or show.get("name"),
        "url": (item.get("external_urls") or {}).get("spotify"),
        "image": image.get("url") or ((item.get("images") or [{}])[0]).get("url"),
        "duration": item.get("duration_ms"),
    }


async def _remember(cache, track):
    saved = await cache.get(LAST_TRACK_KEY)

    if not saved or saved.get("id") != track.get("id"):
        await cache.set(LAST_TRACK_KEY, track, 60 * 60 * 24 * 365)


async def fetch_last_played(config, cache):
    token = await _token(config, cache)

    if not token:
        return None

    headers = {"authorization": f"Bearer {token}"}
    response = await fetch(NOW_PLAYING_URL, headers=headers)

    if response.status == 200:
        data = await response.json()
        item = data.get("item")

        if item:
            track = _track(item)
            playing = bool(data.get("is_playing"))

            await _remember(cache, track)

            return {
                **track,
                "playing": playing,
                "progress": data.get("progress_ms") if playing else None,
                "playedAt": None,
            }

    recent = await fetch(RECENT_URL, headers=headers)

    if recent.status == 200:
        items = (await recent.json()).get("items") or []

        if items and items[0].get("track"):
            track = _track(items[0]["track"])

            await _remember(cache, track)

            return {
                **track,
                "playing": False,
                "progress": None,
                "playedAt": items[0].get("played_at"),
            }

    elif recent.status not in (401, 403):
        raise RuntimeError(f"spotify recently-played returned {recent.status}")

    saved = await cache.get(LAST_TRACK_KEY)

    if saved:
        return {**saved, "playing": False, "progress": None, "playedAt": None}

    return {"missing": True, "scopeError": recent.status in (401, 403)}
