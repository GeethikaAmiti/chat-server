import multiprocessing
import socket
import time
import os
from coordinator import Coordinator
from chat_broker import start_broker
from server import start_server

HOST = "127.0.0.1"

def wait_for_port(port, process):
    """Wait until the process is listening on the requested port."""
    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:
        if not process.is_alive():
            raise RuntimeError(f"Process for port {port} stopped.")

        try:
            with socket.create_connection((HOST, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)

    raise RuntimeError(f"Port {port} did not become available.")

def main():
    try:
        num_servers = int(input("Enter number of servers: "))

        if num_servers < 1:
            print("Please enter a positive number.")
            return

    except ValueError:
        print("Please enter a valid whole number.")
        return

    processes = []

    try:
        # Start the coordinator with the selected server count.
        mode=os.getenv("CHAT_MODE", "threading")
        coordinator_instance = Coordinator(num_servers, mode)
        coordinator = multiprocessing.Process(
            target=coordinator_instance.start
        )
        coordinator.start()
        processes.append(coordinator)
        wait_for_port(5000, coordinator)

        # Start the chat broker.
        broker = multiprocessing.Process(target=start_broker)
        broker.start()
        processes.append(broker)
        wait_for_port(5004, broker)

        # Start the requested number of servers.
        port = 5001

        for i in range(num_servers):
            if port == 5004:
                port += 1

            name = f"Server {i + 1}"

            process = multiprocessing.Process(
                target=start_server,
                args=(name, port),
            )
            process.start()
            processes.append(process)

            port += 1

        # Keep the system running.
        for process in processes:
            process.join()

    except KeyboardInterrupt:
        print("\nStopping chat system...")

    except Exception as error:
        print(f"Startup error: {error}")

    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()

        for process in processes:
            process.join()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
