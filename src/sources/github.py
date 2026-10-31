import json
from datetime import date

from workers import fetch

ENDPOINT = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  rateLimit { limit cost remaining resetAt }
  user(login: $login) {
    login
    name
    bio
    company
    location
    websiteUrl
    twitterUsername
    pronouns
    avatarUrl
    createdAt
    updatedAt
    isHireable
    isCampusExpert
    isDeveloperProgramMember
    isGitHubStar
    isBountyHunter
    status { message emoji }
    followers { totalCount }
    following { totalCount }
    organizations(first: 1) { totalCount }
    gists(first: 1) { totalCount }
    starredRepositories { totalCount }
    watching { totalCount }
    packages { totalCount }
    projectsV2(first: 1) { totalCount }
    sponsors { totalCount }
    sponsoring { totalCount }
    repositoriesContributedTo(first: 1) { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        isHalloween
        weeks {
          contributionDays { date contributionCount weekday }
        }
      }
      contributionYears
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      totalRepositoriesWithContributedCommits
      totalRepositoriesWithContributedIssues
      totalRepositoriesWithContributedPullRequests
      totalRepositoriesWithContributedPullRequestReviews
      restrictedContributionsCount
      hasAnyContributions
      hasActivityInThePast
    }
    repos: repositories(
      first: 100
      ownerAffiliations: OWNER
      isFork: false
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      totalCount
      totalDiskUsage
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        nameWithOwner
        description
        stargazerCount
        forkCount
        diskUsage
        isArchived
        isTemplate
        isPrivate
        pushedAt
        createdAt
        primaryLanguage { name color }
        licenseInfo { name spdxId }
        repositoryTopics(first: 10) {
          nodes { topic { name } }
        }
      }
    }
  }
}
"""


def _calendar_stats(calendar):
    days = [
        day
        for week in calendar.get("weeks") or []
        for day in week.get("contributionDays") or []
    ]
    days.sort(key=lambda day: day["date"])

    if not days:
        return {
            "total": calendar.get("totalContributions", 0),
            "isHalloween": calendar.get("isHalloween", False),
            "currentStreak": 0,
            "longestStreak": 0,
            "bestDay": None,
            "activeDays": 0,
            "days": 0,
            "averagePerDay": 0,
            "weekdayCounts": [0] * 7,
            "weekdayContributions": 0,
            "weekendContributions": 0,
            "firstDay": None,
            "lastDay": None,
        }

    best = max(days, key=lambda day: day["contributionCount"])
    active = [day for day in days if day["contributionCount"] > 0]

    longest = 0
    run = 0

    for day in days:
        if day["contributionCount"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    end = len(days) - 1

    if days[end]["contributionCount"] == 0:
        end -= 1

    current = 0

    for index in range(end, -1, -1):
        if days[index]["contributionCount"] > 0:
            current += 1
        else:
            break

    weekday_counts = [0] * 7

    for day in days:
        weekday = date.fromisoformat(day["date"]).weekday()
        weekday_counts[weekday] += day["contributionCount"]

    total = calendar.get("totalContributions", 0)

    return {
        "total": total,
        "isHalloween": calendar.get("isHalloween", False),
        "currentStreak": current,
        "longestStreak": longest,
        "bestDay": {
            "date": best["date"],
            "count": best["contributionCount"],
        },
        "activeDays": len(active),
        "days": len(days),
        "averagePerDay": round(total / len(days), 2),
        "weekdayCounts": weekday_counts,
        "weekdayContributions": sum(weekday_counts[:5]),
        "weekendContributions": sum(weekday_counts[5:]),
        "firstDay": days[0]["date"],
        "lastDay": days[-1]["date"],
        "contributionDays": [
            {
                "date": day["date"],
                "count": day["contributionCount"],
                "weekday": day["weekday"],
            }
            for day in days
        ],
    }


def _repo_stats(nodes):
    languages = {}
    licenses = {}
    topics = {}
    archived = 0
    templates = 0
    private = 0
    total_disk_usage = 0
    last_pushed = None
    oldest = None
    newest = None

    for node in nodes:
        language = node.get("primaryLanguage")

        if language:
            entry = languages.setdefault(
                language["name"],
                {
                    "name": language["name"],
                    "color": language.get("color"),
                    "repos": 0,
                    "stars": 0,
                },
            )
            entry["repos"] += 1
            entry["stars"] += node.get("stargazerCount", 0)

        license_info = node.get("licenseInfo")

        if license_info:
            name = license_info.get("name") or license_info.get("spdxId")

            if name:
                licenses[name] = licenses.get(name, 0) + 1

        for topic_node in (node.get("repositoryTopics") or {}).get("nodes") or []:
            name = (topic_node.get("topic") or {}).get("name")

            if name:
                topics[name] = topics.get(name, 0) + 1

        if node.get("isArchived"):
            archived += 1

        if node.get("isTemplate"):
            templates += 1

        if node.get("isPrivate"):
            private += 1

        total_disk_usage += node.get("diskUsage") or 0

        pushed = node.get("pushedAt")

        if pushed and (last_pushed is None or pushed > last_pushed["pushedAt"]):
            last_pushed = {
                "name": node.get("nameWithOwner"),
                "pushedAt": pushed,
            }

        created = node.get("createdAt")

        if created:
            repo = {
                "name": node.get("nameWithOwner"),
                "createdAt": created,
            }

            if oldest is None or created < oldest["createdAt"]:
                oldest = repo

            if newest is None or created > newest["createdAt"]:
                newest = repo

    top_languages = sorted(
        languages.values(),
        key=lambda item: (-item["repos"], -item["stars"], item["name"]),
    )
    top_topics = sorted(topics.items(), key=lambda item: (-item[1], item[0]))
    top_licenses = sorted(licenses.items(), key=lambda item: (-item[1], item[0]))

    return {
        "languages": top_languages,
        "topLanguage": top_languages[0] if top_languages else None,
        "licenses": [{"name": name, "repos": count} for name, count in top_licenses],
        "topics": [{"name": name, "repos": count} for name, count in top_topics[:20]],
        "topicCount": len(topics),
        "topicOccurrences": sum(topics.values()),
        "archived": archived,
        "templates": templates,
        "private": private,
        "totalDiskUsage": total_disk_usage,
        "lastPushed": last_pushed,
        "oldestRepo": oldest,
        "newestRepo": newest,
    }


def _top_repos(nodes):
    return [
        {
            "name": node.get("name"),
            "nameWithOwner": node.get("nameWithOwner"),
            "description": node.get("description"),
            "stars": node.get("stargazerCount", 0),
            "forks": node.get("forkCount", 0),
            "language": (node.get("primaryLanguage") or {}).get("name"),
            "languageColor": (node.get("primaryLanguage") or {}).get("color"),
            "isArchived": node.get("isArchived", False),
            "pushedAt": node.get("pushedAt"),
        }
        for node in nodes[:5]
    ]


async def fetch_stats(config):
    if not config.github_token:
        return None

    response = await fetch(
        ENDPOINT,
        method="POST",
        headers={
            "authorization": f"bearer {config.github_token}",
            "content-type": "application/json",
            "user-agent": "spreadsheets600-api",
        },
        body=json.dumps({"query": QUERY, "variables": {"login": config.github_login}}),
    )

    if response.status != 200:
        raise RuntimeError(f"github returned {response.status}")

    payload = await response.json()

    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "github error"))

    user = payload["data"]["user"]

    if not user:
        raise RuntimeError(f"github user not found: {config.github_login}")

    contributions = user["contributionsCollection"]
    repos = user["repos"]
    nodes = repos["nodes"]
    calendar = _calendar_stats(contributions["contributionCalendar"])
    repo_stats = _repo_stats(nodes)
    status = user.get("status") or {}

    return {
        "login": user["login"],
        "name": user["name"],
        "bio": user.get("bio"),
        "company": user.get("company"),
        "location": user.get("location"),
        "websiteUrl": user.get("websiteUrl"),
        "twitterUsername": user.get("twitterUsername"),
        "pronouns": user.get("pronouns"),
        "avatarUrl": user.get("avatarUrl"),
        "createdAt": user["createdAt"],
        "updatedAt": user.get("updatedAt"),
        "isHireable": user.get("isHireable", False),
        "isCampusExpert": user.get("isCampusExpert", False),
        "isDeveloperProgramMember": user.get("isDeveloperProgramMember", False),
        "isGitHubStar": user.get("isGitHubStar", False),
        "isBountyHunter": user.get("isBountyHunter", False),
        "status": {
            "message": status.get("message"),
            "emoji": status.get("emoji"),
        },
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "repos": repos["totalCount"],
        "stars": sum(node["stargazerCount"] for node in nodes),
        "forks": sum(node["forkCount"] for node in nodes),
        "contributions": calendar["total"],
        "commits": contributions["totalCommitContributions"],
        "pullRequests": contributions["totalPullRequestContributions"],
        "issues": contributions["totalIssueContributions"],
        "reviews": contributions["totalPullRequestReviewContributions"],
        "contributedTo": user["repositoriesContributedTo"]["totalCount"],
        "organizations": user["organizations"]["totalCount"],
        "gists": user["gists"]["totalCount"],
        "starred": user["starredRepositories"]["totalCount"],
        "watching": user["watching"]["totalCount"],
        "packages": user["packages"]["totalCount"],
        "projects": user["projectsV2"]["totalCount"],
        "sponsors": user["sponsors"]["totalCount"],
        "sponsoring": user["sponsoring"]["totalCount"],
        "repositoryContributions": contributions["totalRepositoryContributions"],
        "restrictedContributions": contributions["restrictedContributionsCount"],
        "repositoriesWithCommits": contributions[
            "totalRepositoriesWithContributedCommits"
        ],
        "repositoriesWithIssues": contributions[
            "totalRepositoriesWithContributedIssues"
        ],
        "repositoriesWithPullRequests": contributions[
            "totalRepositoriesWithContributedPullRequests"
        ],
        "repositoriesWithReviews": contributions[
            "totalRepositoriesWithContributedPullRequestReviews"
        ],
        "contributionYears": contributions["contributionYears"],
        "hasAnyContributions": contributions["hasAnyContributions"],
        "hasActivityInThePast": contributions["hasActivityInThePast"],
        "currentStreak": calendar["currentStreak"],
        "longestStreak": calendar["longestStreak"],
        "bestDay": calendar["bestDay"],
        "activeDays": calendar["activeDays"],
        "averagePerDay": calendar["averagePerDay"],
        "weekdayCounts": calendar["weekdayCounts"],
        "weekdayContributions": calendar["weekdayContributions"],
        "weekendContributions": calendar["weekendContributions"],
        "calendar": calendar,
        "totalDiskUsage": repos.get("totalDiskUsage"),
        "repoPage": repos.get("pageInfo"),
        "languages": repo_stats["languages"],
        "topLanguage": repo_stats["topLanguage"],
        "licenses": repo_stats["licenses"],
        "topics": repo_stats["topics"],
        "topicCount": repo_stats["topicCount"],
        "topicOccurrences": repo_stats["topicOccurrences"],
        "archived": repo_stats["archived"],
        "templates": repo_stats["templates"],
        "private": repo_stats["private"],
        "repoDiskUsage": repo_stats["totalDiskUsage"],
        "lastPushed": repo_stats["lastPushed"],
        "oldestRepo": repo_stats["oldestRepo"],
        "newestRepo": repo_stats["newestRepo"],
        "topRepos": _top_repos(nodes),
        "rateLimit": payload["data"].get("rateLimit"),
    }
