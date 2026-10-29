import socket
import threading
import time
from collections import deque
from stats_manager import record_approach, record_lost

class Coordinator:
    def __init__(self, num_servers=3, mode="threading"):
        self.host = "127.0.0.1"
        self.port = 5000
        self.capacity = 1 if mode=="iterative" else 3
    
        self.wait_timeout = 5 * 60

        # Create the requested number of servers.
        self.servers = {}
        port = 5001

        for i in range(num_servers):
            if port == 5004:
                port += 1

            name = f"Server {i + 1}"
            self.servers[name] = {
                "port": port,
                "active": 0,
            }
            port += 1

        self.waiting_queue = deque()
        self.condition = threading.Condition()

    def available_server(self):
        """Return a server with an available slot, if one exists."""
        for name, server in self.servers.items():
            if server["active"] < self.capacity:
                return name, server

        return None

    def dispatch(self):
        """Assign available servers to waiting clients in FIFO order."""
        while self.waiting_queue:
            available = self.available_server()

            if available is None:
                break

            entry = self.waiting_queue.popleft()
            name, server = available

            server["active"] += 1
            entry["assignment"] = (name, server["port"])
            entry["status"] = "assigned"

        self.condition.notify_all()

    def handle_assignment(self, connection):
        """Wait for an available server or until the client times out."""
        record_approach()

        entry = {
            "start": time.monotonic(),
            "status": "waiting",
            "assignment": None,
        }

        with self.condition:
            self.waiting_queue.append(entry)
            self.dispatch()

            if entry["status"] == "waiting":
                print(f"[QUEUE] Client waiting | "f"Position: {self.waiting_queue.index(entry) + 1}")

            while entry["status"] == "waiting":
                remaining = self.wait_timeout - (
                    time.monotonic() - entry["start"]
                )

                if remaining <= 0:
                    self.waiting_queue.remove(entry)
                    entry["status"] = "timeout"
                    record_lost()
                    print("Client timed out and was marked as lost.")

                    self.dispatch()
                    break

                self.condition.wait(timeout=remaining)

            status = entry["status"]
            assignment = entry["assignment"]

        if status == "assigned":
            name, port = assignment

            try:
                connection.sendall(f"{name}|{port}\n".encode())
            except OSError:
                with self.condition:
                    self.servers[name]["active"] -= 1
                    self.dispatch()

        elif status == "timeout":
            try:
                connection.sendall(b"TIMEOUT\n")
            except OSError:
                pass

    def handle_request(self, connection):
        """Handle a client assignment request or server slot release."""
        with connection:
            reader = connection.makefile("r", encoding="utf-8")

            try:
                request = reader.readline().strip()

                if request == "ASSIGN":
                    self.handle_assignment(connection)

                elif request.startswith("RELEASE "):
                    name = request.removeprefix("RELEASE ").strip()

                    with self.condition:
                        if (
                            name in self.servers
                            and self.servers[name]["active"] > 0
                        ):
                            self.servers[name]["active"] -= 1
                            print(
                                f"Active sessions on {name}: "
                                f"{self.servers[name]['active']}"
                            )
                            self.dispatch()

            finally:
                reader.close()

    def start(self):
        """Start the coordinator and accept incoming connections."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen()

            print(f"Coordinator listening on {self.host}:{self.port}")

            while True:
                connection, _ = server.accept()

                threading.Thread(
                    target=self.handle_request,
                    args=(connection,),
                    daemon=True,
                ).start()

if __name__ == "__main__":
    coordinator = Coordinator()
    coordinator.start()
