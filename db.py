"""Tiny SQLite store for daily numbers (screen time, workouts, steps, ...).

One row per (day, metric, device). Posting the same key again overwrites it,
so a phone or laptop script can safely re-send today's total as often as it likes.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "personal.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    day    TEXT NOT NULL,
    metric TEXT NOT NULL,
    device TEXT NOT NULL DEFAULT '',
    value  REAL NOT NULL,
    note   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (day, metric, device)
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        c.execute(SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


def upsert(day: str, metric: str, value: float, device: str = "", note: str = "") -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO entries (day, metric, device, value, note)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(day, metric, device)
               DO UPDATE SET value = excluded.value, note = excluded.note""",
            (day, metric, device, value, note),
        )


def date_range(days: int) -> list[str]:
    end = date.today()
    return [(end - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def series(metric: str, days: int = 30) -> dict:
    """Daily values for the last `days` days, one list per device.

    Days with no data are None so charts can show gaps instead of fake zeros.
    """
    labels = date_range(days)
    with conn() as c:
        rows = c.execute(
            "SELECT day, device, value FROM entries WHERE metric = ? AND day >= ?",
            (metric, labels[0]),
        ).fetchall()
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        out.setdefault(r["device"] or "all", {})[r["day"]] = r["value"]
    return {
        "metric": metric,
        "days": labels,
        "series": {dev: [vals.get(d) for d in labels] for dev, vals in out.items()},
    }


def day_total(metric: str, day: str) -> float | None:
    with conn() as c:
        row = c.execute(
            "SELECT SUM(value) AS v FROM entries WHERE metric = ? AND day = ?",
            (metric, day),
        ).fetchone()
    return row["v"]


def daily_totals(metric: str, days: int) -> list[float | None]:
    """Per-day totals across all devices (None where nothing was logged)."""
    s = series(metric, days)
    n = len(s["days"])
    totals: list[float | None] = [None] * n
    for vals in s["series"].values():
        for i, v in enumerate(vals):
            if v is not None:
                totals[i] = (totals[i] or 0) + v
    return totals


def clear_notes(note: str) -> int:
    with conn() as c:
        cur = c.execute("DELETE FROM entries WHERE note = ?", (note,))
        return cur.rowcount
