from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    github_login: str
    github_token: str | None
    wakatime_api_key: str | None
    steam_api_key: str | None
    steam_id: str | None
    spotify_client_id: str | None
    spotify_client_secret: str | None
    spotify_refresh_token: str | None
    discord_id: str | None
    anilist_username: str
    wallpaper_repo: str
    wallpaper_branch: str
    wallpaper_dir: str
    profile_repo: str
    profile_branch: str


def _get(env, name, default=""):
    try:
        value = getattr(env, name)

    except Exception:
        return default

    if value is None:
        return default

    return str(value)


def load(env):
    return Config(
        github_login=_get(env, "GITHUB_LOGIN", "SpreadSheets600"),
        github_token=_get(env, "GITHUB_TOKEN") or None,
        wakatime_api_key=_get(env, "WAKATIME_API_KEY") or None,
        steam_api_key=_get(env, "STEAM_API_KEY") or None,
        steam_id=_get(env, "STEAM_ID") or None,
        spotify_client_id=_get(env, "SPOTIFY_CLIENT_ID") or None,
        spotify_client_secret=_get(env, "SPOTIFY_CLIENT_SECRET") or None,
        spotify_refresh_token=_get(env, "SPOTIFY_REFRESH_TOKEN") or None,
        discord_id=_get(env, "DISCORD_ID") or None,
        anilist_username=_get(env, "ANILIST_USERNAME", "SpreadSheeets"),
        wallpaper_repo=_get(env, "WALLPAPER_REPO", "SpreadSheets600/Wallpapers"),
        wallpaper_branch=_get(env, "WALLPAPER_BRANCH", "gh-pages"),
        wallpaper_dir=_get(env, "WALLPAPER_DIR", "thumbs"),
        profile_repo=_get(env, "PROFILE_REPO", "SpreadSheets600/SpreadSheets600"),
        profile_branch=_get(env, "PROFILE_BRANCH", "main"),
    )
