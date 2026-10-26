import fcntl
from pathlib import Path
from datetime import datetime

ARCHIVE_FILE = Path(__file__).parent / "archive.log"


def log_event(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} | {message}\n"

    with open(ARCHIVE_FILE, "a", encoding="utf-8") as file:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)

        try:
            file.write(entry)
            file.flush()
        finally:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
