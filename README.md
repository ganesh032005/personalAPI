# Ganesh's Personal API

A FastAPI app that serves info about me, live GitHub stats, and daily numbers
(screen time, workouts, anything) with a charts dashboard.

## Run

```bash
pip install -r requirements.txt
export API_KEY="pick-a-long-random-string"   # needed only for writing data
# optional: export GITHUB_TOKEN="..."         # raises GitHub rate limit to 5,000/hour
uvicorn main:app --reload
```

- Dashboard: http://127.0.0.1:8000/dashboard
- Interactive docs: http://127.0.0.1:8000/docs

To preview the dashboard with fake numbers: `python seed_demo.py`
(remove them later with `python seed_demo.py --clear`; real data is kept).

## Endpoints

| Endpoint | Returns |
|---|---|
| `/about`, `/skills`, `/projects`, `/links`, `/interests`, `/fun-fact` | Static info from `data.json` |
| `/github` | Profile, repo count, language mix, recent repos |
| `/github/repos` | All public repos |
| `/github/activity?days=30` | Commits per day (public push events, ~90 days kept by GitHub) |
| `/stats/summary` | Today's screen time and workout, 7-day average, workout streak |
| `/stats/{metric}?days=30` | Daily series per device, e.g. `/stats/screen_time_min` |
| `POST /log` | Save one daily value (needs `X-API-Key`) |
| `POST /log/bulk` | Save up to 500 values (needs `X-API-Key`) |
| `/dashboard` | Charts page |

## Logging data

One row per day + metric + device. Sending the same key again overwrites it,
so a script can re-send today's running total as often as it likes.

```bash
curl -X POST http://127.0.0.1:8000/log \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"metric": "screen_time_min", "device": "phone", "value": 245}'

curl -X POST http://127.0.0.1:8000/log \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"metric": "workout_min", "value": 40, "note": "legs"}'
```

Metric names: lowercase letters, digits, underscores. The dashboard charts
`screen_time_min` (per device) and `workout_min`; any other metric is stored
and available at `/stats/{metric}`.

## Content

Static info (name, projects, links) lives in `data.json`; edit and refresh.
Replace the `TODO` entries in `interests` and `fun_facts`.

## Deploy

Render, Railway or Fly.io work. Start command:
`uvicorn main:app --host 0.0.0.0 --port $PORT`

Set `API_KEY` (and optionally `GITHUB_TOKEN`) as environment variables. The
SQLite file is `personal.db`; on hosts with an ephemeral disk, attach a
persistent volume and point `DB_PATH` at it, or your logs will reset on redeploy.
