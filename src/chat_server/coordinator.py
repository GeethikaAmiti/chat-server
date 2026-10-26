import socket
import threading
import time
from collections import deque

from stats_manager import record_approach, record_lost

HOST = "127.0.0.1"
PORT = 5000
CAPACITY = 1
WAIT_TIMEOUT = 15

servers = {
    "Server A": {"port": 5001, "active": 0},
    "Server B": {"port": 5002, "active": 0},
    "Server C": {"port": 5003, "active": 0},
}

waiting_queue = deque()
condition = threading.Condition()


def available_server():
    for name, details in servers.items():
        if details["active"] < CAPACITY:
            return name, details

    return None


def dispatch():
    while waiting_queue:
        available = available_server()

        if available is None:
            break

        entry = waiting_queue[0]

        name, details = available
        details["active"] += 1

        entry["assignment"] = (name, details["port"])
        entry["status"] = "assigned"
        waiting_queue.popleft()

    condition.notify_all()


def handle_assignment(connection):
    record_approach()

    entry = {
        "start": time.monotonic(),
        "status": "waiting",
        "assignment": None,
    }

    with condition:
        waiting_queue.append(entry)
        print(f"Client queued. Position: {len(waiting_queue)}")

        dispatch()

        while entry["status"] == "waiting":
            remaining = WAIT_TIMEOUT - (
                time.monotonic() - entry["start"]
            )

            if remaining <= 0:
                waiting_queue.remove(entry)
                entry["status"] = "timeout"
                record_lost()
                print("Client timed out and was marked as lost.")
                break

            condition.wait(timeout=remaining)

        status = entry["status"]
        assignment = entry["assignment"]

    if status == "assigned":
        name, port = assignment

        try:
            connection.sendall(f"{name}|{port}\n".encode())
        except OSError:
            with condition:
                servers[name]["active"] -= 1
                dispatch()

    elif status == "timeout":
        try:
            connection.sendall(b"TIMEOUT\n")
        except OSError:
            pass


def handle_request(connection):
    with connection:
        reader = connection.makefile("r", encoding="utf-8")

        try:
            request = reader.readline().strip()

            if request == "ASSIGN":
                handle_assignment(connection)

            elif request.startswith("RELEASE "):
                name = request.removeprefix("RELEASE ").strip()

                with condition:
                    if (
                        name in servers
                        and servers[name]["active"] > 0
                    ):
                        servers[name]["active"] -= 1
                        print(
                            f"Released slot on {name}: "
                            f"{servers[name]['active']}"
                        )
                        dispatch()

        finally:
            reader.close()


def start_coordinator():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()

        print(f"Coordinator listening on {HOST}:{PORT}")

        while True:
            connection, _ = server.accept()

            threading.Thread(
                target=handle_request,
                args=(connection,),
                daemon=True,
            ).start()


if __name__ == "__main__":
    start_coordinator()
