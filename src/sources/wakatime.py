import base64

from workers import fetch

BASE = "https://wakatime.com/api/v1"


def _headers(config):
    encoded = base64.b64encode(config.wakatime_api_key.encode()).decode()
    return {"authorization": f"Basic {encoded}"}


async def fetch_stats(config):
    if not config.wakatime_api_key:
        return None

    headers = _headers(config)

    lifetime = await fetch(
        f"{BASE}/users/current/all_time_since_today",
        headers=headers,
    )

    if lifetime.status != 200:
        raise RuntimeError(f"wakatime lifetime returned {lifetime.status}")

    lifetime_data = await lifetime.json()

    week = await fetch(
        f"{BASE}/users/current/summaries?range=last_7_days",
        headers=headers,
    )

    if week.status != 200:
        raise RuntimeError(f"wakatime week returned {week.status}")

    week_data = await week.json()

    days = week_data.get("data") or []
    languages = {}
    editors = {}

    for day in days:
        for language in day.get("languages") or []:
            name = language.get("name", "Other")
            languages[name] = languages.get(name, 0) + language.get("total_seconds", 0)

        for editor in day.get("editors") or []:
            name = editor.get("name", "Other")
            editors[name] = editors.get(name, 0) + editor.get("total_seconds", 0)

    top_languages = sorted(languages.items(), key=lambda item: item[1], reverse=True)
    top_editors = sorted(editors.items(), key=lambda item: item[1], reverse=True)

    return {
        "total": (lifetime_data.get("data") or {}).get("text", "0 hrs"),
        "totalSeconds": (lifetime_data.get("data") or {}).get("total_seconds", 0),
        "weekSeconds": sum(
            (day.get("grand_total") or {}).get("total_seconds", 0) for day in days
        ),
        "daily": [
            {
                "date": (day.get("range") or {}).get("date"),
                "seconds": (day.get("grand_total") or {}).get("total_seconds", 0),
            }
            for day in days
        ],
        "languages": [
            {"name": name, "seconds": seconds} for name, seconds in top_languages[:5]
        ],
        "editors": [
            {"name": name, "seconds": seconds} for name, seconds in top_editors[:3]
        ],
    }
