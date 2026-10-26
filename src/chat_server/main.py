import multiprocessing
import socket
import time

from coordinator import start_coordinator
from server import start_server


HOST = "127.0.0.1"
COORDINATOR_PORT = 5000


def wait_for_coordinator(process):
    deadline = time.monotonic() + 5

    while time.monotonic() < deadline:
        if not process.is_alive():
            raise RuntimeError("Coordinator process exited unexpectedly.")

        try:
            with socket.create_connection(
                (HOST, COORDINATOR_PORT), timeout=0.2
            ):
                return
        except OSError:
            time.sleep(0.1)

    raise RuntimeError("Coordinator did not start within 5 seconds.")


def main():
    processes = []

    coordinator = multiprocessing.Process(
        target=start_coordinator,
        name="Coordinator",
    )
    processes.append(coordinator)
    coordinator.start()

    try:
        wait_for_coordinator(coordinator)

        servers = [
            ("Server A", 5001),
            ("Server B", 5002),
            ("Server C", 5003),
        ]

        for name, port in servers:
            process = multiprocessing.Process(
                target=start_server,
                args=(name, port),
                name=name,
            )
            processes.append(process)
            process.start()

        for process in processes:
            process.join()

    except KeyboardInterrupt:
        print("\nStopping coordinator and servers...")

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