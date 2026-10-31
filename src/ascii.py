import unicodedata

INNER = 42


def _char_width(char):
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def _width(text):
    return sum(_char_width(char) for char in text)


def _fit(text, limit):
    text = str(text)

    if _width(text) <= limit:
        return text

    kept = []
    used = 0

    for char in text:
        width = _char_width(char)

        if used + width > limit - 3:
            break

        kept.append(char)
        used += width

    return "".join(kept) + "..."


def _pad(text, limit):
    return text + " " * max(0, limit - _width(text))


def _line(label, value):
    body = f" {label:<8} {_fit(value, INNER - 10)}"
    return "│" + _pad(body, INNER) + "│"


def _data(snapshot, key):
    entry = snapshot.get(key) or {}
    return entry.get("data") or {}


def render(snapshot):
    anilist = _data(snapshot, "anilist")
    steam = _data(snapshot, "steam")
    github = _data(snapshot, "github")
    spotify = _data(snapshot, "spotify")
    wakatime = _data(snapshot, "wakatime")

    lines = ["┌─ SOHAM " + "─" * (INNER - 8) + "┐"]

    if github:
        lines.append(
            _line(
                "github",
                f"{github.get('contributions', 0):,} contributions"
                f" · {github.get('stars', 0):,} stars",
            )
        )
        lines.append(
            _line(
                "repos",
                f"{github.get('repos', 0):,} · {github.get('forks', 0):,} forks"
                f" · {github.get('contributedTo', 0):,} contributed",
            )
        )
        lines.append(
            _line(
                "social",
                f"{github.get('followers', 0):,} followers"
                f" · {github.get('reviews', 0):,} reviews",
            )
        )
        lines.append(
            _line(
                "streak",
                f"{github.get('currentStreak', 0)}d now"
                f" · {github.get('longestStreak', 0)}d best",
            )
        )

        language = github.get("topLanguage") or {}

        if language.get("name"):
            lines.append(
                _line(
                    "lang",
                    f"{language['name']} · {language.get('repos', 0)} repos",
                )
            )

    if wakatime:
        languages = len(wakatime.get("languages") or [])
        lines.append(
            _line(
                "code",
                f"{wakatime.get('total', '0 hrs')} · {languages} langs",
            )
        )

    if anilist:
        anime = anilist.get("anime") or {}
        manga = anilist.get("manga") or {}

        if anime:
            lines.append(
                _line(
                    "anime",
                    f"{anime.get('count', 0):,} series"
                    f" · {anime.get('episodesWatched', 0):,} eps",
                )
            )

        if manga:
            lines.append(
                _line(
                    "manga",
                    f"{manga.get('count', 0):,} · {manga.get('chaptersRead', 0):,} ch",
                )
            )

        watching = anilist.get("watching") or []

        if watching:
            first = watching[0]
            episodes = first.get("episodes")
            progress = first.get("progress", 0)
            suffix = f"{progress}/{episodes}" if episodes else f"{progress} eps"
            lines.append(
                _line(
                    "watching",
                    f"{first.get('title', '')} · {suffix}",
                )
            )

    if steam:
        activity = steam.get("game") or steam.get("status") or "offline"
        lines.append(_line("steam", activity))

        if steam.get("ownedGames"):
            lines.append(
                _line(
                    "library",
                    f"{steam.get('ownedGames', 0):,} games"
                    f" · lvl {steam.get('level', 0)}"
                    f" · {steam.get('totalHours', 0):,} hrs",
                )
            )

        achievements = steam.get("achievements") or {}

        if achievements.get("total"):
            lines.append(
                _line(
                    "achv",
                    f"{achievements.get('unlocked', 0):,}"
                    f"/{achievements.get('total', 0):,}"
                    f" · {achievements.get('perfect', 0)} perfect",
                )
            )

        rarest = achievements.get("rarest") or {}

        if rarest.get("name"):
            lines.append(
                _line(
                    "rarest",
                    f"{rarest['name']} · {rarest.get('percent', 0)}%",
                )
            )

    if spotify:
        if spotify.get("playing"):
            lines.append(
                _line(
                    "spotify",
                    f"{spotify.get('title', '')} - {spotify.get('artists', '')}",
                )
            )
        else:
            lines.append(_line("spotify", "not playing"))

    if len(lines) == 1:
        lines.append(_line("status", "no sources configured"))

    lines.append("└" + "─" * INNER + "┘")
    return "\n".join(lines)
