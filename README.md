# spreadsheets600-api

A small all-in-one profile API running on **Cloudflare Workers (Python)**. It
powers the [SpreadSheets600 profile README](https://github.com/SpreadSheets600/SpreadSheets600).

`/snapshot` is the primary API: it returns one JSON object with GitHub, WakaTime,
Steam, Spotify, AniList, and Discord data. `/discord` and `/spotify` render live
SVG cards that can be dropped straight into a README. `/ascii` is only one text
renderer on top of the snapshot.

The profile repo has a GitHub Action that calls this API, refreshes the AniList
cache, and writes the result into its README twice a day, so GitHub's image cache
never serves a stale card.

## Routes

| Route | What it returns |
| --- | --- |
| `GET /` | Service name and the route list |
| `GET /health` | Which sources are configured, plus the current UTC time |
| `GET /header` | `302` to a random wallpaper |
| `GET /header?format=json` | `{ "path": "...", "url": "..." }` |
| `GET /header?dir=headers` | Override the wallpaper folder for one request |
| `GET /pfp` | `302` to the GitHub avatar |
| `GET /ascii` | Plain-text terminal card (the current minimal renderer) |
| `GET /snapshot` | Full JSON for GitHub, WakaTime, Steam, Spotify, AniList, and Discord |
| `GET /discord` | Live Discord card as SVG: avatar, status, clan tag, profile badges and current activity (`?theme=dark\|light`) |
| `GET /spotify` | Current or last played Spotify card as SVG (`?theme=dark\|light`) |

JSON and text responses send `access-control-allow-origin: *`. `OPTIONS`
requests return `204`, so the API can be called from a browser or another
frontend.

## API-first usage

Fetch the whole snapshot:

```bash
export BASE=https://spreadsheets600-api-io.spreadsheets600.workers.dev

curl -s "$BASE/snapshot" | jq .
```

The response is shaped like this:

```json
{
  "generatedAt": "2026-10-29T07:07:10Z",
  "github":   { "ok": true, "data": { "...": "..." } },
  "wakatime": { "ok": true, "data": { "...": "..." } },
  "steam":    { "ok": true, "data": { "...": "..." } },
  "spotify":  { "ok": true, "data": { "...": "..." } },
  "anilist":  { "ok": true, "data": { "...": "..." } },
  "discord":  { "ok": true, "data": { "presence": { "...": "..." }, "profile": { "...": "..." } } }
}
```

Each source is independent. A missing token or a failing upstream returns
`{ "ok": false, "data": null, "error": "..." }` for that source only; the rest of
the snapshot still works.

Useful `jq` queries:

```bash
# GitHub summary
curl -s "$BASE/snapshot" | jq '.github.data | {
  contributions, stars, forks, followers, repos,
  currentStreak, longestStreak, topLanguage
}'

# Steam library and achievements
curl -s "$BASE/snapshot" | jq '.steam.data | {
  ownedGames, level, badges, totalHours, backlog,
  recent, topGames, achievements
}'

# WakaTime
curl -s "$BASE/snapshot" | jq '.wakatime.data'

# Spotify: now playing plus the last played track
curl -s "$BASE/snapshot" | jq '.spotify.data | { playing, title, artists, lastPlayed }'

# Discord: presence from Lanyard, and the raw dcdn.dstn.to profile
curl -s "$BASE/snapshot" | jq '.discord.data.presence | { name, status, tag, activity, custom }'
curl -s "$BASE/snapshot" | jq '.discord.data.profile | { badges, user_profile, premium_since }'

# AniList anime and manga totals plus the latest anime and manga entries
curl -s "$BASE/snapshot" | jq '.anilist.data | {
  user, anime, manga, latestAnime, latestManga
}'
```

`/snapshot` is cached for 15 minutes. If you are building a custom card or graph,
read `/snapshot` directly instead of scraping `/ascii`; that way you can use the
full dataset without changing the text renderer.

## GitHub stats

`/snapshot` returns a detailed `github.data` object. `/ascii` only renders a few
of these fields.

| Group | Fields |
| --- | --- |
| Profile | `bio`, `company`, `location`, `websiteUrl`, `twitterUsername`, `pronouns`, `avatarUrl`, `createdAt`, `updatedAt`, `status`, profile flags |
| Counts | `followers`, `following`, `repos`, `stars`, `forks`, `contributedTo`, `organizations`, `gists`, `starred`, `watching`, `packages`, `projects`, `sponsors`, `sponsoring` |
| Contributions | `contributions`, `commits`, `pullRequests`, `issues`, `reviews`, `repositoryContributions`, `restrictedContributions`, `repositoriesWithCommits`, `repositoriesWithIssues`, `repositoriesWithPullRequests`, `repositoriesWithReviews`, `contributionYears`, activity flags |
| Calendar | `currentStreak`, `longestStreak`, `bestDay`, `activeDays`, `averagePerDay`, `weekdayCounts`, `weekdayContributions`, `weekendContributions`, `contributionDays` (date/count/weekday for each day), plus the raw `calendar` block |
| Repositories | `totalDiskUsage` (all repos), `repoDiskUsage` (first 100), `archived`, `templates`, `private`, `languages`, `topLanguage`, `licenses`, `topics`, `topicCount`, `topicOccurrences`, `lastPushed`, `oldestRepo`, `newestRepo`, `topRepos`, `repoPage` |
| Meta | `rateLimit` |

`weekdayCounts` is ordered Monday → Sunday. Repository-level `stars`, `forks`,
language and topic aggregates cover the first 100 owned, non-fork repositories
ordered by stars. `repos` and `totalDiskUsage` cover the whole account.
Pagination (`repoPage`) is exposed if exact totals across every repository are
needed later.

Per-repository connections such as `watchers`, open `issues`, open
`pullRequests`, `discussions`, `releases` and `packages` are intentionally not
in the main query: adding four of them across 100 repositories pushed the query
past GitHub's timeout. Fetch them later in a separate paginated query, or only
for the top N repositories.

## Steam stats

`/snapshot` returns `steam.data` with the library, profile, and achievement data
below.

| Group | Fields |
| --- | --- |
| Profile | `name`, `avatar`, `profileUrl`, `country`, `status`, `game`, `level`, `xp`, `xpNeeded`, `badges` |
| Library | `ownedGames`, `totalMinutes`, `totalHours`, `averageHours`, `backlog`, `recent`, `topGames` |
| Achievements | `checked`, `unlocked`, `total`, `percent`, `perfect`, `perfectGames`, `latest`, `rarest`, `games` |

`recent` contains the last five played games with two-week and total playtime.
`topGames` contains the five most-played games. `backlog` counts owned games with
zero recorded playtime.

Achievement data is fetched for the top five most-played games plus recent games,
capped at `ACHIEVEMENT_GAME_LIMIT` (8) appids. Each appid costs one subrequest
for `GetPlayerAchievements` and one for the global rarity percentages. That keeps
the worker under Cloudflare's per-request subrequest limit. `checked` tells you
how many games were inspected, and `perfect` / `rarest` only cover those games.
To inspect the whole 125-game library, use a separate scheduled job that writes
to KV instead of doing it inside `/snapshot`.

Steam profile game details must be public. If `GetOwnedGames` returns
`game_count: 0`, check Steam → Privacy Settings → **Game details**. Games without
stats, or games whose details are private, are skipped when
`GetPlayerAchievements` returns `success: false`.

## AniList stats

AniList returns `403` to requests from Cloudflare Workers, so the worker does not
call the GraphQL API directly. Instead, `.github/scripts/anilist_source.py` in the profile repo runs
in its **Update profile** GitHub Action, fetches the public AniList API from a
GitHub runner, normalises the response, and commits it to
`assets/anilist.json`. The worker reads that public file and exposes it as
`anilist.data` in `/snapshot`.

| Group | Fields |
| --- | --- |
| Profile | `user.id`, `user.name`, `user.about`, `user.avatar`, `user.bannerImage`, `user.createdAt`, `user.updatedAt` |
| Anime | `count`, `meanScore`, `minutesWatched`, `hoursWatched`, `daysWatched`, `episodesWatched`, `statuses`, `genres` |
| Manga | `count`, `meanScore`, `chaptersRead`, `volumesRead`, `statuses`, `genres` |
| Latest | `latestAnime` and `latestManga`: `mediaId`, `title`, `status`, `progress`, `total`, `updatedAt`, `cover` (inline data URI) |

`statuses` is a list of `{ status, count, meanScore }` entries. `genres` is
sorted by title count and includes `minutesWatched` for anime. `latestAnime` / `latestManga` hold the most recently updated entry
that has progress.

The cache is refreshed twice a day by the profile action. To refresh it
immediately, run **Actions → Update profile → Run workflow**. After the first
`assets/anilist.json` commit, clear the `snapshot` KV key (see below) or wait for
the 15-minute TTL so `/snapshot` picks it up.

## Cards

`/discord` and `/spotify` return `image/svg+xml`. Images (avatar, album art,
badges) are embedded as data URIs, so the cards work inside a README `<img>`,
which cannot load remote images from inside an SVG. They are transparent and take
`?theme=dark` or `?theme=light`, so a `<picture>` element can switch them with the
reader's colour scheme:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://YOUR-WORKER/discord?theme=dark">
  <img alt="Discord status" src="https://YOUR-WORKER/discord?theme=light" width="100%">
</picture>
```

The same markup works for `/spotify`. Discord data is cached for 20 seconds and
Spotify for 45; GitHub's image proxy adds its own caching on top, so a README
refreshes within a minute or so rather than instantly.

## Discord

Presence comes from [Lanyard](https://github.com/Phineas/lanyard), so the user has
to be in the Lanyard Discord server. Profile details (badges, theme colours, bio,
nameplate, display name styles, connected accounts) come from the public
`https://dcdn.dstn.to/profile/{id}` endpoint and are cached for an hour.

`discord.data` in `/snapshot` has two keys:

- `presence`: `name`, `username`, `status`, `avatarUrl`, `decorationUrl`, `tag`,
  `badgeUrl`, `activity` and `custom` (custom status). Music ("listening")
  activities are left out on purpose; use the Spotify source for that.
- `profile`: the dcdn response as returned, or `null` if it is unavailable.

Activity privacy matters: if Lanyard reports no activities while the Discord
client shows one, turn on **Settings → Activity Privacy → Share my activity** and
check that the game is enabled under **Registered Games**.

## WakaTime and Spotify

`wakatime.data` contains:

- `total`, `totalSeconds`: all-time coding time
- `weekSeconds`: the last seven days
- `daily`: one `{ date, seconds }` entry per day for the last seven days
- `languages`: top five languages for the week
- `editors`: top three editors for the week

`spotify.data` contains:

- `playing`, `title`, `artists`, `album`, `url`, `image`
- `progress`, `duration` in milliseconds
- `lastPlayed`: the current track while playing, otherwise the most recent track
  (`title`, `artists`, `album`, `url`, `image`, `duration`, `playing`, `playedAt`)

When Spotify is not playing, the top-level fields are `{ "playing": false }` and
`lastPlayed` still holds the last track. `lastPlayed` uses the recently-played
endpoint; if the token lacks that scope the worker falls back to the last track it
saw while playing, which it keeps in KV.

## Local development

```bash
uv sync
cp .dev.vars.example .dev.vars   # fill in the values you have
uv run pywrangler dev
```

Test it:

```bash
curl http://localhost:8787/health
curl http://localhost:8787/header?format=json
curl http://localhost:8787/ascii
curl http://localhost:8787/snapshot
```

## Configuration

Public values live in `wrangler.toml` under `[vars]`:

- `GITHUB_LOGIN`, `STEAM_ID`, `ANILIST_USERNAME`, `DISCORD_ID`
- `WALLPAPER_REPO`, `WALLPAPER_BRANCH`, `WALLPAPER_DIR`
- `PROFILE_REPO`, `PROFILE_BRANCH`

`ANILIST_USERNAME` is the public AniList username used by the profile action.
The worker also uses it as an enable flag for the cached AniList source.

Secrets are set with `pywrangler`:

```bash
uv run pywrangler secret put GITHUB_TOKEN
uv run pywrangler secret put WAKATIME_API_KEY
uv run pywrangler secret put STEAM_API_KEY
uv run pywrangler secret put SPOTIFY_CLIENT_ID
uv run pywrangler secret put SPOTIFY_CLIENT_SECRET
uv run pywrangler secret put SPOTIFY_REFRESH_TOKEN
```

### GitHub token

Create a fine-grained personal access token with read access to public
repositories and the user profile. The worker uses it for the GraphQL stats and
for the wallpaper tree (unauthenticated tree calls are rate-limited).

### WakaTime

WakaTime's docs now prefer OAuth tokens for reads; the legacy API key still
works with Basic auth and is what the existing README action uses. If reads start
failing, generate an OAuth token and use it in place of the key.

### Steam

Create a Steam Web API key at <https://steamcommunity.com/dev/apikey>. The
worker uses it for the player summary, owned games, recently played games, Steam
level, badges, achievements, and global achievement percentages.

### Spotify

The refresh token must include the `user-read-currently-playing` and
`user-read-recently-played` scopes. The
worker stores rotated refresh tokens in KV when a `CACHE` binding exists.

## KV cache

`wrangler.toml` already binds a `CACHE` namespace. It shares cached API responses
between isolates and persists Spotify refresh-token rotation. To recreate it in
another Cloudflare account:

```bash
uv run pywrangler kv namespace create CACHE
```

Paste the returned namespace id into the `[[kv_namespaces]]` block in
`wrangler.toml`. KV is optional: without the binding the worker falls back to a
per-isolate memory cache.

The snapshot cache key is `snapshot` with a 15-minute TTL. To force a refresh
after a deploy or data change:

```bash
npx --yes wrangler kv key delete snapshot \
  --namespace-id bf0ca021ee8f4079bc99dac7a2df75ef \
  --remote
```

## Deploy

Manual deploy:

```bash
npx wrangler login   # once per machine
uv sync
uv run pywrangler deploy
```

Use `pywrangler`, not plain `wrangler deploy`: it vendors the `workers` SDK into
`python_modules/` (gitignored) before uploading, and a plain deploy from a clean
checkout fails with `No module named 'workers'`.

### Automatic deploys from GitHub

Connect the repo to the Worker with Cloudflare Workers Builds:

1. Cloudflare dashboard → **Workers & Pages** → `spreadsheets600-api-io` →
   **Settings → Builds → Connect**.
2. Pick **GitHub** and this repository, branch `main`.
3. Build command: leave empty. Deploy command: `uv run pywrangler deploy`.
4. Save. Every push to `main` now builds and deploys the Worker.

Secrets and `[vars]` stay on the Worker, so they are not touched by a deploy.

### Using it from the profile repo

The profile README action needs to know where the Worker lives. In the profile
repo add an Actions variable `PROFILE_API_BASE` (**Settings → Secrets and
variables → Actions → Variables**) with the deployed URL, e.g.
`https://spreadsheets600-api-io.<subdomain>.workers.dev`. The action runs at
**00:30 and 12:30 UTC** and commits README, chart, and AniList cache changes only
when the generated output differs.

## ASCII card

The current `/ascii` route is a deliberately small text renderer. It is not the
API contract; `/snapshot` is. If you want a richer layout, build it on top of
`/snapshot` (or add a new renderer module) and keep `/ascii` as a fallback.

## Wallpapers

`/header` picks a random image from `WALLPAPER_DIR` on `WALLPAPER_BRANCH` of
`WALLPAPER_REPO` (currently `Wallpapers/` on `master`). Files over 4.5 MB are
skipped because GitHub refuses to proxy README images larger than 5 MB. The
profile action writes the returned URL into the header block of its README.

## Notes

- AniList is fetched by the profile repo's action, not by the worker: AniList
  blocks Cloudflare Workers egress with a `403`. The action commits
  `assets/anilist.json`, and the worker reads that public cache.
- Python Workers run on Pyodide; cold starts are slower than JavaScript, which is
  why every source is cached for 15 minutes.
- The worker has no third-party Python dependencies, so deploys stay small and
  fast.
