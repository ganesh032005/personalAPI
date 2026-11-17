"""Public GitHub data for a user, cached so the API doesn't burn rate limits.

Works without a token (60 requests/hour). Set GITHUB_TOKEN for 5,000/hour.
"""
import os
import time
from collections import Counter
from datetime import date, timedelta

import httpx

API = "https://api.github.com"
TTL_SECONDS = 600
_cache: dict[str, tuple[float, object]] = {}


def _get(path: str, params: dict | None = None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "personal-api"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = httpx.get(API + path, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def _cached(key: str, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL_SECONDS:
        return hit[1]
    value = fn()
    _cache[key] = (time.time(), value)
    return value


def repos(username: str) -> list[dict]:
    def load():
        raw = _get(f"/users/{username}/repos", {"per_page": 100, "sort": "pushed"})
        return [
            {
                "name": r["name"],
                "description": r["description"],
                "language": r["language"],
                "stars": r["stargazers_count"],
                "forks": r["forks_count"],
                "pushed_at": r["pushed_at"],
                "url": r["html_url"],
                "is_fork": r["fork"],
            }
            for r in raw
        ]

    return _cached(f"repos:{username}", load)


def profile(username: str) -> dict:
    def load():
        u = _get(f"/users/{username}")
        return {
            "username": u["login"],
            "name": u["name"],
            "bio": u["bio"],
            "public_repos": u["public_repos"],
            "followers": u["followers"],
            "following": u["following"],
            "url": u["html_url"],
        }

    return _cached(f"profile:{username}", load)


def summary(username: str) -> dict:
    rs = repos(username)
    own = [r for r in rs if not r["is_fork"]]
    langs = Counter(r["language"] for r in own if r["language"])
    return {
        **profile(username),
        "languages": dict(langs.most_common()),
        "recent_repos": rs[:6],
    }


def activity(username: str, days: int = 30) -> dict:
    """Commits per day from the public events feed (GitHub keeps ~90 days)."""

    def load():
        events = []
        for page in (1, 2, 3):
            batch = _get(f"/users/{username}/events/public", {"per_page": 100, "page": page})
            events.extend(batch)
            if len(batch) < 100:
                break
        return events

    events = _cached(f"events:{username}", load)
    per_day: Counter = Counter()
    for e in events:
        if e["type"] == "PushEvent":
            payload = e.get("payload", {})
            per_day[e["created_at"][:10]] += payload.get("size") or 1

    end = date.today()
    labels = [(end - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    return {"days": labels, "commits": [per_day.get(d, 0) for d in labels]}
