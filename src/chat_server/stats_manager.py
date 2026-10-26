import json
import fcntl
from pathlib import Path
from datetime import datetime
from threading import Lock

FILE = Path(__file__).parent / "server_stats.json"
LOCK_FILE = Path(__file__).parent / "server_stats.json.lock"

lock = Lock()


def read_data():
    if FILE.exists():
        with open(FILE, encoding="utf-8") as file:
            return json.load(file)

    return {
        "totals": {"approached": 0, "lost": 0},
        "servers": {},
        "sessions": [],
    }


def update_data(action):
    """Safely read and update statistics across processes."""
    with lock, open(LOCK_FILE, "a") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        try:
            data = read_data()

            # Support existing JSON files that lack global counters.
            data.setdefault("totals", {"approached": 0, "lost": 0})
            data.setdefault("servers", {})
            data.setdefault("sessions", [])

            action(data)

            temporary = FILE.with_suffix(".tmp")
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)

            temporary.replace(FILE)

        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def record_approach():
    def action(data):
        data["totals"]["approached"] += 1

    update_data(action)


def record_lost():
    def action(data):
        data["totals"]["lost"] += 1

    update_data(action)


def update(server, client, entered, left, duration, messages, rating):
    def action(data):
        stats = data["servers"].setdefault(
            server, {"daily": {}, "monthly": {}}
        )

        periods = [
            (stats["daily"], entered.strftime("%Y-%m-%d")),
            (stats["monthly"], entered.strftime("%Y-%m")),
        ]

        for period, key in periods:
            counts = period.setdefault(
                key,
                {"served": 0, "rating_sum": 0, "ratings": 0},
            )

            # A valid client session counts as served even without a rating.
            counts["served"] += 1

            if rating is not None:
                counts["rating_sum"] += rating
                counts["ratings"] += 1

        data["sessions"].append({
            "client": client,
            "server": server,
            "joined": entered.isoformat(),
            "left": left.isoformat(),
            "duration": round(duration, 2),
            "messages": messages,
            "rating": rating,
        })

    update_data(action)


def get_dashboard(server_name):
    """Return saved statistics for one server."""
    with lock, open(LOCK_FILE, "a") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)

        try:
            data = read_data()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    now = datetime.now()
    stats = data.get("servers", {}).get(
        server_name, {"daily": {}, "monthly": {}}
    )

    today = stats["daily"].get(
        now.strftime("%Y-%m-%d"),
        {"served": 0, "rating_sum": 0, "ratings": 0},
    )

    month = stats["monthly"].get(
        now.strftime("%Y-%m"),
        {"served": 0, "rating_sum": 0, "ratings": 0},
    )

    average = (
        today["rating_sum"] / today["ratings"]
        if today["ratings"] else None
    )

    return {
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "served_today": today["served"],
        "served_month": month["served"],
        "average_rating": average,
        "approached": data["totals"]["approached"],
        "lost": data["totals"]["lost"],
    }
