from datetime import datetime
from threading import Lock

class StatsTracker:
    def __init__(self):
        self.lock = Lock()
        self.total_seen = 0
        self.dropped_clients = 0

    def inc_seen(self):
        with self.lock:
            self.total_seen += 1

    def inc_dropped(self):
        with self.lock:
            self.dropped_clients += 1

    def print_summary(self, servers):
        # Copy the counters while locked, then print without holding the lock.
        with self.lock:
            total_seen = self.total_seen
            dropped = self.dropped_clients

        print("\n=== SERVER STATISTICS ===")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Clients approached: {total_seen}")
        print(f"Lost clients:       {dropped}")

        for server in servers:
            active_names = [
                client.client_name
                for client in server.current_clients
            ]

            print(f"\n{server.name}")
            print(f"  Active clients: {len(active_names)}")
            print(f"  Client names:   {', '.join(active_names) or 'None'}")
            print(f"  Clients served: {server.total_clients}")
            print(f"  Average rating: {server.average_rating:.2f}/5")

        print("=========================\n")
