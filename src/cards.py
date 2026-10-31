import asyncio
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from images import data_uri
from sources import discord, spotify

FONT = 'ui-sans-serif, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif'
WIDTH = 800
PAD = 24

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "fg": "#e6edf3",
        "muted": "#8b949e",
        "track": "#232a33",
        "line": "#3d444d",
    },
    "light": {
        "bg": "#ffffff",
        "fg": "#1f2328",
        "muted": "#656d76",
        "track": "#e8ebef",
        "line": "#d1d9e0",
    },
}

STATUS = {
    "online": "#23a55a",
    "idle": "#f0b232",
    "dnd": "#f23f43",
    "offline": "#80848e",
}
SPOTIFY_GREEN = "#1db954"
VERBS = {
    "playing": "Playing",
    "streaming": "Streaming",
    "watching": "Watching",
    "competing": "Competing in",
}


class Svg:
    def __init__(self, width, height, theme, label):
        self.width, self.height, self.theme, self.label = width, height, theme, label
        self.parts = []
        self.defs = []

    def text(
        self,
        x,
        y,
        value,
        size=13,
        weight=400,
        fill=None,
        anchor="start",
        italic=False,
        spacing=None,
    ):
        extra = f' letter-spacing="{spacing}"' if spacing else ""
        extra += ' font-style="italic"' if italic else ""
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill or self.theme["fg"]}" text-anchor="{anchor}"{extra}>'
            f"{escape(str(value))}</text>"
        )

    def rect(self, x, y, w, h, fill, rx=0):
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"/>'
        )

    def circle(self, cx, cy, r, fill, stroke=None, width=2):
        outline = f' stroke="{stroke}" stroke-width="{width}"' if stroke else ""
        self.parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"{outline}/>'
        )

    def image(self, x, y, w, h, href, radius=0, circular=False):
        clip_id = f"clip{len(self.defs)}"
        shape = (
            f'<circle cx="{x + w / 2}" cy="{y + h / 2}" r="{w / 2}"/>'
            if circular
            else f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}"/>'
        )
        self.defs.append(f'<clipPath id="{clip_id}">{shape}</clipPath>')
        self.parts.append(
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="{href}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{clip_id})"/>'
        )

    def render(self):
        defs = f"<defs>{''.join(self.defs)}</defs>\n" if self.defs else ""
        body = defs + "\n".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}" role="img" aria-label="{escape(self.label)}" '
            f"font-family='{FONT}'>\n{body}\n</svg>\n"
        )


def fit(value, size, width):
    value = str(value or "")
    limit = max(int(width / (size * 0.56)), 4)

    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def ago(iso):
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))

    except (AttributeError, ValueError):
        return None

    seconds = int((datetime.now(timezone.utc) - then).total_seconds())

    if seconds < 90:
        return "just now"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes}m ago"

    hours = minutes // 60

    if hours < 24:
        return f"{hours}h ago"

    return f"{hours // 24}d ago"


def clock(milliseconds):
    seconds = int((milliseconds or 0) // 1000)

    return f"{seconds // 60}:{seconds % 60:02d}"


def notice(message, theme_name, label):
    theme = THEMES[theme_name]
    svg = Svg(WIDTH, 96, theme, label)
    svg.text(WIDTH / 2, 54, message, size=13, fill=theme["muted"], anchor="middle")

    return svg.render()


def discord_card(data, images, theme_name):
    theme = THEMES[theme_name]
    svg = Svg(WIDTH, 208, theme, "Discord status")
    cx, cy = 68, 54

    if images.get("avatar"):
        svg.image(cx - 32, cy - 32, 64, 64, images["avatar"], circular=True)

    else:
        svg.circle(cx, cy, 32, theme["track"])

    if images.get("decoration"):
        svg.image(cx - 40, cy - 40, 80, 80, images["decoration"])

    svg.circle(
        cx + 24,
        cy + 24,
        10,
        STATUS.get(data["status"], STATUS["offline"]),
        stroke=theme["bg"],
        width=3,
    )

    if data["status"] == "dnd":
        svg.rect(cx + 19, cy + 22.5, 10, 3, theme["bg"], rx=1.5)

    x = 122
    name = fit(data["name"], 22, 380)
    svg.text(x, 50, name, size=22, weight=700)

    cursor = x + len(name) * 22 * 0.7 + 18

    if data.get("tag"):
        tag_width = (22 if images.get("badge") else 10) + len(data["tag"]) * 7.8 + 12
        svg.rect(cursor, 32, tag_width, 24, theme["track"], rx=12)
        text_x = cursor + 10

        if images.get("badge"):
            svg.image(cursor + 8, 37, 14, 14, images["badge"])
            text_x = cursor + 28

        svg.text(text_x, 49, data["tag"], size=12, weight=600)
        cursor += tag_width + 10

    for badge in images.get("badges") or []:
        svg.image(cursor, 34, 20, 20, badge)
        cursor += 26

    svg.text(x, 76, f"@{data['username']}", size=13, fill=theme["muted"])
    svg.rect(PAD, 108, WIDTH - 2 * PAD, 1, theme["line"])

    activity, custom = data.get("activity"), data.get("custom")

    if activity:
        left = PAD

        if images.get("activity"):
            svg.image(PAD, 126, 64, 64, images["activity"], radius=8)
            left = PAD + 64 + 16

        room = WIDTH - PAD - left
        svg.text(
            left,
            138,
            VERBS.get(activity["kind"], "Playing").upper(),
            size=11,
            weight=600,
            fill=theme["muted"],
            spacing="0.08em",
        )
        svg.text(left, 160, fit(activity["name"], 16, room), size=16, weight=700)

        if activity.get("details"):
            svg.text(
                left,
                178,
                fit(activity["details"], 13, room),
                size=13,
                fill=theme["muted"],
            )

        if activity.get("state"):
            svg.text(
                left,
                195,
                fit(activity["state"], 13, room),
                size=13,
                fill=theme["muted"],
            )

    elif custom and custom.get("text"):
        text = fit(custom["text"], 15, WIDTH - 2 * PAD - 40)
        shift = 14 if (custom.get("emoji") or images.get("emoji")) else 0
        span = len(text) * 15 * 0.56 / 2

        if images.get("emoji"):
            svg.image(WIDTH / 2 + shift - span - 26, 146, 22, 22, images["emoji"])

        elif custom.get("emoji"):
            svg.text(WIDTH / 2 + shift - span - 26, 164, custom["emoji"], size=18)

        svg.text(WIDTH / 2 + shift, 164, text, size=15, anchor="middle")

    else:
        svg.text(
            WIDTH / 2,
            164,
            "I'm not currently doing anything!",
            size=13,
            fill=theme["muted"],
            anchor="middle",
            italic=True,
        )

    return svg.render()


def spotify_card(track, cover, theme_name):
    theme = THEMES[theme_name]

    if not track or track.get("missing"):
        message = (
            "Re-authorise Spotify with the user-read-recently-played scope"
            if track and track.get("scopeError")
            else "Nothing played yet"
        )

        return notice(message, theme_name, "Spotify")

    svg = Svg(WIDTH, 148, theme, "Spotify last played")
    x = PAD + 100 + 24
    room = WIDTH - PAD - x

    if cover:
        svg.image(PAD, 24, 100, 100, cover, radius=10)

    else:
        svg.rect(PAD, 24, 100, 100, theme["track"], rx=10)

    svg.circle(x + 4, 34, 4, SPOTIFY_GREEN if track["playing"] else theme["muted"])
    svg.text(
        x + 16,
        38,
        "NOW PLAYING" if track["playing"] else "LAST PLAYED",
        size=11,
        weight=600,
        fill=theme["muted"],
        spacing="0.08em",
    )
    svg.text(x, 68, fit(track["title"], 19, room), size=19, weight=700)
    svg.text(x, 90, fit(track["artists"], 14, room), size=14, fill=theme["muted"])

    if track.get("album"):
        svg.text(x, 110, fit(track["album"], 12, room), size=12, fill=theme["muted"])

    if track["playing"] and track.get("duration") and track.get("progress") is not None:
        fraction = min(track["progress"] / track["duration"], 1)
        svg.rect(x, 122, room, 4, theme["track"], rx=2)
        svg.rect(x, 122, max(room * fraction, 4), 4, SPOTIFY_GREEN, rx=2)
        svg.text(x, 141, clock(track["progress"]), size=11, fill=theme["muted"])
        svg.text(
            x + room,
            141,
            clock(track["duration"]),
            size=11,
            fill=theme["muted"],
            anchor="end",
        )

    else:
        when = ago(track.get("playedAt"))

        if when:
            svg.text(x, 134, f"Played {when}", size=12, fill=theme["muted"])

    return svg.render()


async def discord_svg(config, cache, theme_name):
    data = await cache.get("card:discord")

    if not data:
        data = await discord.fetch_presence(config)

        if not data:
            return notice("Discord is not configured", theme_name, "Discord status")

        data["profile"] = await discord.fetch_profile(config, cache)
        await cache.set("card:discord", data, 20, persist=False)

    profile = data.get("profile") or {}
    activity = data.get("activity") or {}
    custom = data.get("custom") or {}
    badge_urls = [badge["url"] for badge in profile.get("badges") or []]
    avatar, decoration, badge, art, emoji, *badges = await asyncio.gather(
        data_uri(cache, data["avatarUrl"]),
        data_uri(cache, data["decorationUrl"]),
        data_uri(cache, data["badgeUrl"]),
        data_uri(cache, activity.get("image")),
        data_uri(cache, custom.get("emojiUrl")),
        *(data_uri(cache, url) for url in badge_urls),
    )
    images = {
        "avatar": avatar,
        "decoration": decoration,
        "badge": badge,
        "activity": art,
        "emoji": emoji,
        "badges": [uri for uri in badges if uri],
    }

    return discord_card(data, images, theme_name)


async def spotify_svg(config, cache, theme_name):
    track = await cache.get("card:spotify")

    if not track:
        track = await spotify.fetch_last_played(config, cache)

        if not track:
            return notice("Spotify is not configured", theme_name, "Spotify")

        await cache.set("card:spotify", track, 45, persist=False)

    cover = await data_uri(cache, track.get("image")) if track.get("image") else None

    return spotify_card(track, cover, theme_name)
