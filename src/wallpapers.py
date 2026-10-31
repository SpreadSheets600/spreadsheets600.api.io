import random

from workers import fetch

TREE_URL = "https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
RAW_URL = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"

ALLOWED_DIRS = {"thumbs", "headers", "Wallpapers"}
IMAGE_SUFFIXES = (".webp", ".jpg", ".jpeg", ".png")


MAX_BYTES = 4_500_000


async def _list(config, cache, directory):
    key = f"wallpapers:v2:{config.wallpaper_repo}:{config.wallpaper_branch}:{directory}"
    cached = await cache.get(key)

    if cached:
        return cached

    headers = {"User-Agent": "spreadsheets600-api"}

    if config.github_token:
        headers["Authorization"] = f"bearer {config.github_token}"

    url = TREE_URL.format(
        repo=config.wallpaper_repo,
        branch=config.wallpaper_branch,
    )

    response = await fetch(url, headers=headers)

    if response.status in (401, 403, 404) and config.github_token:
        response = await fetch(url, headers={"User-Agent": "profile-api"})

    if response.status != 200:
        raise RuntimeError(f"Wallpaper Tree Returned - {response.status}")

    payload = await response.json()
    prefix = directory.rstrip("/") + "/"

    paths = [
        item["path"]
        for item in payload.get("tree", [])
        if item.get("type") == "blob"
        and item["path"].startswith(prefix)
        and item["path"].lower().endswith(IMAGE_SUFFIXES)
        and item.get("size", 0) <= MAX_BYTES
    ]

    if not paths:
        raise RuntimeError(f"No Wallpapers {prefix}")

    await cache.set(key, paths, 60 * 60 * 24)
    return paths


async def pick(config, cache, directory=None):
    directory = directory or config.wallpaper_dir

    if directory not in ALLOWED_DIRS:
        raise ValueError(f"unsupported wallpaper directory: {directory}")

    paths = await _list(config, cache, directory)
    path = random.choice(paths)

    return {
        "path": path,
        "url": RAW_URL.format(
            repo=config.wallpaper_repo,
            branch=config.wallpaper_branch,
            path=path,
        ),
    }
