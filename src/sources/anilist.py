from workers import fetch

RAW_BASE = "https://raw.githubusercontent.com"


async def fetch_stats(config):

    if not config.anilist_username:
        return None

    url = (
        f"{RAW_BASE}/{config.profile_repo}/{config.profile_branch}/assets/anilist.json"
    )
    response = await fetch(
        url,
        headers={
            "accept": "application/json",
            "user-agent": "spreadsheets600-api",
        },
    )

    if response.status != 200:
        raise RuntimeError(f"anilist cache returned {response.status}")

    payload = await response.json()
    return payload or None
