import json
import os
import random
import re
import secrets
from datetime import date
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import db
import github_stats

BASE = Path(__file__).parent
DATA_FILE = BASE / "data.json"

app = FastAPI(title="Ganesh's Personal API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def load() -> dict:
    # Re-read on every request so edits to data.json show up without a restart.
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def github_user() -> str:
    url = load()["links"]["github"].rstrip("/")
    return url.rsplit("/", 1)[-1]


# ---------- auth for writes ----------

def require_key(x_api_key: str | None = Header(default=None)):
    """Writes need the X-API-Key header to match the API_KEY environment variable."""
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(503, "Writes are disabled: set the API_KEY environment variable")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid or missing X-API-Key")


# ---------- static profile info ----------

@app.get("/")
def root():
    data = load()
    return {
        "message": f"Hi, I'm {data['about']['name']}. This is my personal API.",
        "endpoints": [
            "/about", "/skills", "/projects", "/projects/{name}", "/links",
            "/interests", "/fun-fact",
            "/github", "/github/repos", "/github/activity",
            "/stats/summary", "/stats/{metric}",
            "/dashboard", "/docs",
        ],
    }


@app.get("/about")
def about():
    return load()["about"]


@app.get("/skills")
def skills():
    return load()["skills"]


@app.get("/projects")
def projects():
    return load()["projects"]


@app.get("/projects/{name}")
def project(name: str):
    for p in load()["projects"]:
        if p["name"].lower() == name.lower():
            return p
    raise HTTPException(status_code=404, detail="Project not found")


@app.get("/links")
def links():
    return load()["links"]


@app.get("/interests")
def interests():
    return load()["interests"]


@app.get("/fun-fact")
def fun_fact():
    return {"fact": random.choice(load()["fun_facts"])}


# ---------- live GitHub data ----------

def _gh(fn, *args):
    try:
        return fn(*args)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code in (403, 429):
            raise HTTPException(503, "GitHub rate limit hit; try later or set GITHUB_TOKEN")
        raise HTTPException(502, f"GitHub returned {code}")
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach GitHub")


@app.get("/github")
def github():
    return _gh(github_stats.summary, github_user())


@app.get("/github/repos")
def github_repos():
    return _gh(github_stats.repos, github_user())


@app.get("/github/activity")
def github_activity(days: int = 30):
    days = max(1, min(days, 90))
    return _gh(github_stats.activity, github_user(), days)


# ---------- daily log: screen time, workouts, anything numeric ----------

METRIC_RE = re.compile(r"^[a-z0-9_]{1,40}$")


class LogEntry(BaseModel):
    metric: str = Field(description="e.g. screen_time_min, workout_min, steps")
    value: float
    day: date = Field(default_factory=date.today)
    device: str = Field(default="", max_length=30, description="e.g. phone, laptop")
    note: str = Field(default="", max_length=200)


def _save(e: LogEntry):
    if not METRIC_RE.match(e.metric):
        raise HTTPException(422, "metric must be lowercase letters, digits or underscores")
    db.upsert(e.day.isoformat(), e.metric, e.value, e.device.lower(), e.note)


@app.post("/log", dependencies=[Depends(require_key)])
def log_entry(entry: LogEntry):
    _save(entry)
    return {"saved": 1}


@app.post("/log/bulk", dependencies=[Depends(require_key)])
def log_bulk(entries: list[LogEntry]):
    if len(entries) > 500:
        raise HTTPException(413, "At most 500 entries per request")
    for e in entries:
        _save(e)
    return {"saved": len(entries)}


@app.get("/stats/summary")
def stats_summary():
    today = date.today().isoformat()
    screen7 = [v for v in db.daily_totals("screen_time_min", 7) if v is not None]
    workouts = db.daily_totals("workout_min", 30)

    streak = 0
    # Today may not be logged yet, so start from yesterday in that case.
    for i, v in enumerate(reversed(workouts)):
        if v:
            streak += 1
        elif i == 0:
            continue
        else:
            break

    return {
        "today": {
            "screen_time_min": db.day_total("screen_time_min", today),
            "workout_min": db.day_total("workout_min", today),
        },
        "screen_time_7d_avg_min": round(sum(screen7) / len(screen7)) if screen7 else None,
        "workout_days_30d": sum(1 for v in workouts if v),
        "workout_streak": streak,
    }


@app.get("/stats/{metric}")
def stats(metric: str, days: int = 30):
    if not METRIC_RE.match(metric):
        raise HTTPException(422, "Invalid metric name")
    return db.series(metric, max(1, min(days, 365)))


# ---------- dashboard page ----------

@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(BASE / "static" / "dashboard.html")
