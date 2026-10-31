from workers import fetch

LANYARD = "https://api.lanyard.rest/v1/users/{id}"
CDN = "https://cdn.discordapp.com"
MEDIA = "https://media.discordapp.net"
PROFILE = "https://dcdn.dstn.to/profile/{id}"
PROFILE_KEY = "discord:profile"


def _app_image(activity):
    assets = activity.get("assets") or {}
    image = assets.get("large_image")

    if not image:
        return None

    if image.startswith("mp:"):
        return f"{MEDIA}/{image[3:]}?width=112&height=112"

    if image.isdigit() and activity.get("application_id"):
        return f"{CDN}/app-assets/{activity['application_id']}/{image}.png?size=128"

    return None


def _activity(raw):
    return {
        "kind": {
            0: "playing",
            1: "streaming",
            3: "watching",
            5: "competing",
        }.get(raw.get("type"), "playing"),
        "name": raw.get("name"),
        "details": raw.get("details"),
        "state": raw.get("state"),
        "image": _app_image(raw),
    }


def _custom(raw):
    emoji = raw.get("emoji") or {}
    emoji_url = None

    if emoji.get("id"):
        emoji_url = f"{CDN}/emojis/{emoji['id']}.png?size=48"

    return {
        "text": raw.get("state"),
        "emoji": None if emoji_url else emoji.get("name"),
        "emojiUrl": emoji_url,
    }


async def fetch_presence(config):
    if not config.discord_id:
        return None

    response = await fetch(LANYARD.format(id=config.discord_id))

    if response.status != 200:
        raise RuntimeError(f"lanyard returned {response.status}")

    body = await response.json()

    if not body.get("success"):
        raise RuntimeError("lanyard user not found")

    data = body["data"]
    user = data.get("discord_user") or {}
    activities = data.get("activities") or []
    guild = user.get("primary_guild") or {}
    decoration = user.get("avatar_decoration_data") or {}

    avatar = user.get("avatar")
    avatar_url = (
        f"{CDN}/avatars/{user['id']}/{avatar}.png?size=128"
        if avatar
        else f"{CDN}/embed/avatars/{(int(user['id']) >> 22) % 6}.png"
    )

    custom = next((item for item in activities if item.get("type") == 4), None)
    main = next((item for item in activities if item.get("type") not in (2, 4)), None)

    return {
        "name": user.get("display_name")
        or user.get("global_name")
        or user.get("username"),
        "username": user.get("username"),
        "status": data.get("discord_status", "offline"),
        "avatarUrl": avatar_url,
        "decorationUrl": (
            f"{CDN}/avatar-decoration-presets/{decoration['asset']}.png?size=128&passthrough=false"
            if decoration.get("asset")
            else None
        ),
        "tag": guild.get("tag") if guild.get("identity_enabled") else None,
        "badgeUrl": (
            f"{CDN}/clan-badges/{guild['identity_guild_id']}/{guild['badge']}.png?size=32"
            if guild.get("identity_enabled") and guild.get("badge")
            else None
        ),
        "activity": _activity(main) if main else None,
        "custom": _custom(custom)
        if custom and (custom.get("state") or custom.get("emoji"))
        else None,
    }


async def fetch_profile_raw(config, cache):
    if not config.discord_id:
        return None

    cached = await cache.get(PROFILE_KEY)

    if cached:
        return cached

    try:
        response = await fetch(PROFILE.format(id=config.discord_id))

        if response.status != 200:
            return None

        body = await response.json()

    except Exception as error:
        print(f"Discord Profile Failed: {error}")
        return None

    await cache.set(PROFILE_KEY, body, 3600)

    return body


async def fetch_profile(config, cache):
    body = await fetch_profile_raw(config, cache) or {}

    return {
        "badges": [
            {
                "description": badge.get("description"),
                "url": f"{CDN}/badge-icons/{badge['icon']}.png",
            }
            for badge in body.get("badges") or []
            if badge.get("icon")
        ][:8],
    }


async def fetch_stats(config, cache):
    presence = await fetch_presence(config)

    if presence is None:
        return None

    return {"presence": presence, "profile": await fetch_profile_raw(config, cache)}
