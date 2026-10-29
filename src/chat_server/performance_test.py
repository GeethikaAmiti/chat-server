import time
import subprocess
import psutil

class PerformanceMonitor:
    def __init__(self):
        self.host = "127.0.0.1"
        self.coordinator_port = 5000
        self.broker_port = 5004
        self.processes = {}

    def find_servers(self):
    #Find chat server processes using their listening ports
        self.processes.clear()

        try:
            connections = psutil.net_connections(kind="tcp")
        except psutil.AccessDenied:
            print("Cannot inspect network connections. Check process permissions.")
            return

        for connection in connections:
            if connection.status != psutil.CONN_LISTEN:
                continue

            if not connection.laddr or connection.pid is None:
                continue

            port = connection.laddr.port

        # Chat servers use ports from 5001 onward.
        # Port 5004 belongs to the broker.
            if port < 5001 or port in (self.broker_port, 8089):
                continue

            try:
                process = psutil.Process(connection.pid)
                self.processes[f"Server (port {port})"] = process
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def display_stats(self):
        #Display CPU, memory, and disk I/O for each server
        print("\n========== SERVER PERFORMANCE ==========")

        for name, process in list(self.processes.items()):
            try:
                cpu = process.cpu_percent(interval=None)
                memory = process.memory_info().rss / (1024 * 1024)
                io = process.io_counters()

                print(f"\n{name} (PID: {process.pid})")
                print(f"CPU usage:       {cpu:.1f}%")
                print(f"Memory usage:    {memory:.2f} MB")
                print(f"Disk write ops:  {io.write_count}")
                print(f"Disk bytes:      {io.write_bytes}")

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"\n{name}: Process unavailable")

        print("========================================")

    def run(self):
        self.find_servers()

        if not self.processes:
            print("No servers found. Start main.py first.")
            return

        # Initialize CPU measurements before displaying readings.
        for process in self.processes.values():
            process.cpu_percent(interval=None)

        try:
            while True:
                time.sleep(2)
                self.display_stats()

        except KeyboardInterrupt:
            print("\nMonitoring stopped.")

if __name__ == "__main__":
    PerformanceMonitor().run()
