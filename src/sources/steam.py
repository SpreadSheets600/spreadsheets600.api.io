from urllib.parse import urlencode

from workers import fetch

BASE = "https://api.steampowered.com"

STATUS = {
    0: "offline",
    1: "online",
    2: "busy",
    3: "away",
    4: "snooze",
    5: "looking to trade",
    6: "looking to play",
}


ACHIEVEMENT_GAME_LIMIT = 8
TOP_GAME_LIMIT = 5


async def _get(path, params):
    response = await fetch(f"{BASE}/{path}?{urlencode(params)}")

    if response.status != 200:
        return None

    return await response.json()


def _icon(appid, icon):
    if not icon:
        return None

    return (
        "https://media.steampowered.com/steamcommunity/public/images/apps/"
        f"{appid}/{icon}.jpg"
    )


def _minutes(game, key):
    return game.get(key) or 0


async def _achievements(config, appid):
    data = await _get(
        "ISteamUserStats/GetPlayerAchievements/v1/",
        {
            "key": config.steam_api_key,
            "steamid": config.steam_id,
            "appid": appid,
            "l": "english",
        },
    )

    stats = (data or {}).get("playerstats") or {}

    if not stats.get("success"):
        return None

    achievements = stats.get("achievements") or []

    if not achievements:
        return None

    unlocked = [item for item in achievements if item.get("achieved") == 1]
    latest = max(unlocked, key=lambda item: item.get("unlocktime", 0), default=None)

    return {
        "appid": appid,
        "name": stats.get("gameName"),
        "total": len(achievements),
        "unlocked": len(unlocked),
        "percent": round(len(unlocked) / len(achievements) * 100, 1),
        "perfect": len(unlocked) == len(achievements),
        "latest": (
            {
                "name": latest.get("name"),
                "description": latest.get("description"),
                "unlockedAt": latest.get("unlocktime"),
            }
            if latest
            else None
        ),
        "items": [
            {"apiname": item.get("apiname"), "name": item.get("name")}
            for item in unlocked
        ],
    }


async def _rarity(config, appid):
    data = await _get(
        "ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/",
        {"gameid": appid},
    )

    rows = ((data or {}).get("achievementpercentages") or {}).get("achievements") or []

    return {row.get("name"): row.get("percent") for row in rows}


async def fetch_stats(config):
    if not config.steam_api_key or not config.steam_id:
        return None

    summary = await _get(
        "ISteamUser/GetPlayerSummaries/v2/",
        {"key": config.steam_api_key, "steamids": config.steam_id},
    )

    players = ((summary or {}).get("response") or {}).get("players") or []

    if not players:
        raise RuntimeError("Steam Player Not Found")

    player = players[0]

    owned_data = await _get(
        "IPlayerService/GetOwnedGames/v1/",
        {
            "key": config.steam_api_key,
            "steamid": config.steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "include_free_sub": 1,
        },
    )

    owned = (owned_data or {}).get("response") or {}
    games = owned.get("games") or []

    recent_data = await _get(
        "IPlayerService/GetRecentlyPlayedGames/v1/",
        {
            "key": config.steam_api_key,
            "steamid": config.steam_id,
            "count": 5,
        },
    )

    recent_games = ((recent_data or {}).get("response") or {}).get("games") or []

    level_data = await _get(
        "IPlayerService/GetSteamLevel/v1/",
        {"key": config.steam_api_key, "steamid": config.steam_id},
    )

    level = ((level_data or {}).get("response") or {}).get("player_level", 0)

    badges_data = await _get(
        "IPlayerService/GetBadges/v1/",
        {"key": config.steam_api_key, "steamid": config.steam_id},
    )

    badge_response = (badges_data or {}).get("response") or {}
    badges = badge_response.get("badges") or []

    total_minutes = sum(_minutes(game, "playtime_forever") for game in games)

    top_games = sorted(
        games,
        key=lambda game: _minutes(game, "playtime_forever"),
        reverse=True,
    )[:TOP_GAME_LIMIT]

    played = [game for game in games if game.get("rtime_last_played")]
    last_played = max(played, key=lambda game: game["rtime_last_played"], default=None)
    latest_game = (recent_games or [None])[0] or last_played

    recent = [
        {
            "appid": game.get("appid"),
            "name": game.get("name"),
            "minutes": game.get("playtime_2weeks", 0),
            "totalMinutes": game.get("playtime_forever", 0),
            "icon": _icon(game.get("appid"), game.get("img_icon_url")),
        }
        for game in recent_games
    ]

    candidates = []

    for game in top_games + recent_games:
        appid = game.get("appid")

        if appid and appid not in candidates:
            candidates.append(appid)

    achievement_games = []

    for appid in candidates[:ACHIEVEMENT_GAME_LIMIT]:
        result = await _achievements(config, appid)

        if result:
            achievement_games.append(result)

    rarest = None

    for result in achievement_games:
        percentages = await _rarity(config, result["appid"])

        for item in result["items"]:
            percent = percentages.get(item.get("apiname"))

            if percent is None:
                continue

            try:
                percent = float(percent)

            except ValueError:
                continue

            if rarest is None or percent < rarest["percent"]:
                rarest = {
                    "name": item.get("name"),
                    "game": result["name"],
                    "percent": round(percent, 1),
                }

    for result in achievement_games:
        result.pop("items", None)

    unlocked = sum(result["unlocked"] for result in achievement_games)
    total = sum(result["total"] for result in achievement_games)
    perfect = [result for result in achievement_games if result["perfect"]]

    latest = max(
        (
            {**result["latest"], "game": result["name"]}
            for result in achievement_games
            if result.get("latest")
        ),
        key=lambda item: item.get("unlockedAt", 0),
        default=None,
    )

    return {
        "name": player.get("personaname"),
        "avatar": player.get("avatarfull"),
        "profileUrl": player.get("profileurl"),
        "country": player.get("loccountrycode"),
        "status": STATUS.get(player.get("personastate", 0), "offline"),
        "game": player.get("gameextrainfo"),
        "level": level,
        "xp": badge_response.get("player_xp", 0),
        "xpNeeded": badge_response.get("player_xp_needed_to_level_up", 0),
        "badges": len(badges),
        "ownedGames": owned.get("game_count", len(games)),
        "totalMinutes": total_minutes,
        "totalHours": round(total_minutes / 60),
        "averageHours": round(total_minutes / 60 / len(games), 1) if games else 0,
        "backlog": sum(1 for game in games if _minutes(game, "playtime_forever") == 0),
        "recent": recent,
        "latestPlayed": {
            "appid": latest_game.get("appid"),
            "name": latest_game.get("name"),
            "minutes": latest_game.get("playtime_forever", 0),
            "hours": round(latest_game.get("playtime_forever", 0) / 60),
            "recentMinutes": latest_game.get("playtime_2weeks", 0),
            "lastPlayed": latest_game.get("rtime_last_played"),
        }
        if latest_game
        else None,
        "topGames": [
            {
                "appid": game.get("appid"),
                "name": game.get("name"),
                "minutes": game.get("playtime_forever", 0),
                "hours": round(game.get("playtime_forever", 0) / 60),
                "lastPlayed": game.get("rtime_last_played"),
                "icon": _icon(game.get("appid"), game.get("img_icon_url")),
            }
            for game in top_games
        ],
        "achievements": {
            "checked": len(achievement_games),
            "unlocked": unlocked,
            "total": total,
            "percent": round(unlocked / total * 100, 1) if total else 0,
            "perfect": len(perfect),
            "perfectGames": [result["name"] for result in perfect],
            "latest": latest,
            "rarest": rarest,
            "games": achievement_games,
        },
    }
