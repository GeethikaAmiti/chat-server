import threading
from archive_logger import log_event

THREADS = 10
MESSAGES_PER_THREAD = 100


def write_messages(thread_id):
    for i in range(MESSAGES_PER_THREAD):
        log_event(f"Thread {thread_id}: message {i}")


threads = [
    threading.Thread(target=write_messages, args=(i,))
    for i in range(THREADS)
]

for thread in threads:
    thread.start()

for thread in threads:
    thread.join()

print("Concurrent archive test completed.")