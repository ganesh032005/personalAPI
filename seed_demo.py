"""Fill the database with fake numbers so you can see the dashboard working.

    python seed_demo.py           # add 30 days of demo data
    python seed_demo.py --clear   # remove only the demo rows (real data is kept)
"""
import random
import sys
from datetime import date, timedelta

import db

NOTE = "demo"

if "--clear" in sys.argv:
    print(f"Removed {db.clear_notes(NOTE)} demo rows")
    sys.exit()

random.seed(7)
for i in range(30):
    day = (date.today() - timedelta(days=i)).isoformat()
    db.upsert(day, "screen_time_min", random.randint(150, 330), "phone", NOTE)
    db.upsert(day, "screen_time_min", random.randint(180, 420), "laptop", NOTE)
    if random.random() < 0.6:
        db.upsert(day, "workout_min", random.choice([25, 30, 40, 45, 60]), "", NOTE)
print("Seeded 30 days of demo data")
