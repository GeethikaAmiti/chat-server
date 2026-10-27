import time
import subprocess
import psutil

class PerformanceMonitor:
    def __init__(self):
        self.servers = {
            "Server A": 5001,
            "Server B": 5002,
            "Server C": 5003,
        }
        self.processes = {}

    def find_servers(self):
        """Find the process ID of each server."""
        for name, port in self.servers.items():
            result = subprocess.run(
                ["fuser", f"{port}/tcp"],
                capture_output=True,
                text=True,
            )

            for pid in result.stdout.split():
                try:
                    self.processes[name] = psutil.Process(int(pid))
                    break
                except (psutil.NoSuchProcess, ValueError):
                    continue

    def display_stats(self):
        """Display CPU, memory, and disk I/O for each server."""
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