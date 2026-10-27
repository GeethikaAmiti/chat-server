import multiprocessing
import socket
import time

from coordinator import Coordinator
from chat_broker import start_broker
from server import start_server

HOST = "127.0.0.1"


def wait_for_port(port, process):
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
    processes = []


    try:
        coordinator_instance=Coordinator()
        coordinator = multiprocessing.Process(target=coordinator_instance.start)
        coordinator.start()
        processes.append(coordinator)
        wait_for_port(5000, coordinator)

        broker = multiprocessing.Process(target=start_broker)
        broker.start()
        processes.append(broker)
        wait_for_port(5004, broker)

        for name, port in [
            ("Server A", 5001),
            ("Server B", 5002),
            ("Server C", 5003),
        ]:
            process = multiprocessing.Process(
                target=start_server,
                args=(name, port),
            )
            process.start()
            processes.append(process)

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