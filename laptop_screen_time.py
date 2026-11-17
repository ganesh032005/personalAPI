"""Send today's laptop screen time (from ActivityWatch) to the personal API.

Run it by hand or on a schedule. Each run re-sends today's running total and the
API overwrites that day's value, so running it often is safe.

Needs:
  - ActivityWatch installed and running (https://activitywatch.net)
  - the personal API running
  - the API_KEY environment variable set to the same key the API was started with

Optional environment variables: API_URL, AW_URL, DEVICE_NAME
"""
import os
import sys
from datetime import datetime

import httpx

AW_URL = os.environ.get("AW_URL", "http://localhost:5600")
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("API_KEY")
DEVICE = os.environ.get("DEVICE_NAME", "laptop")


def active_minutes_today(now: datetime) -> float:
    """Minutes today where ActivityWatch saw you at the keyboard (not AFK)."""
    buckets = httpx.get(f"{AW_URL}/api/0/buckets/", timeout=10).json()
    afk_buckets = [b for b in buckets if b.startswith("aw-watcher-afk")]
    if not afk_buckets:
        sys.exit("No ActivityWatch AFK bucket found. Is ActivityWatch running with its watchers?")

    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds = 0.0
    for bucket in afk_buckets:
        events = httpx.get(
            f"{AW_URL}/api/0/buckets/{bucket}/events",
            params={"start": start.isoformat(), "end": now.isoformat(), "limit": -1},
            timeout=30,
        ).json()
        seconds += sum(e["duration"] for e in events if e["data"].get("status") == "not-afk")
    return seconds / 60


def main():
    if not API_KEY:
        sys.exit("Set the API_KEY environment variable first.")

    now = datetime.now().astimezone()
    try:
        minutes = round(active_minutes_today(now))
        r = httpx.post(
            f"{API_URL}/log",
            headers={"X-API-Key": API_KEY},
            json={
                "metric": "screen_time_min",
                "device": DEVICE,
                "value": minutes,
                "day": now.date().isoformat(),
            },
            timeout=10,
        )
    except httpx.ConnectError as e:
        sys.exit(f"Could not connect ({e}). Are ActivityWatch and the API both running?")

    if r.status_code != 200:
        sys.exit(f"API said {r.status_code}: {r.text}")
    print(f"Logged {minutes} min of laptop screen time for {now.date()}")


if __name__ == "__main__":
    main()
