import socket
import threading
import time
from collections import Counter

HOST = "127.0.0.1"
COORDINATOR_PORT = 5000
NUM_CLIENTS = 20
SESSION_DURATION = 3

results = Counter()
results_lock = threading.Lock()


def simulate_client(client_id):
    username = f"TestClient_{client_id}"
    server_name = None
    assigned = False

    try:
        # Request a server assignment.
        with socket.create_connection(
            (HOST, COORDINATOR_PORT), timeout=10
        ) as coordinator:
            coordinator.sendall(b"ASSIGN\n")

            response = coordinator.makefile("r").readline().strip()

        if response == "TIMEOUT":
            outcome = "timed_out"
            return

        if not response or response == "FULL":
            outcome = "rejected"
            return

        server_name, port = response.split("|")
        port = int(port)

        # Connect to the assigned server.
        with socket.create_connection(
            (HOST, port), timeout=10
        ) as client:
            assigned = True
            client.sendall(f"{username}\n".encode())

            # Read the server's greeting.
            client.settimeout(3)
            greeting = client.recv(1024)

            if not greeting:
                outcome = "connection_failed"
                return

            # Keep the session active for the test duration.
            time.sleep(SESSION_DURATION)
            outcome = "assigned"

    except (OSError, ValueError) as error:
        print(f"{username}: {error}")
        outcome = "failed"

    finally:
        with results_lock:
            results[outcome] += 1

            if assigned:
                results[f"{server_name}_assigned"] += 1

        print(f"{username}: {outcome}")


def main():
    started_at = time.monotonic()
    threads = []

    print(f"Starting test with {NUM_CLIENTS} simulated clients...")

    for client_id in range(1, NUM_CLIENTS + 1):
        thread = threading.Thread(
            target=simulate_client,
            args=(client_id,),
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    elapsed = time.monotonic() - started_at

    print("\n=== LOAD TEST RESULTS ===")
    print(f"Clients attempted: {NUM_CLIENTS}")
    print(f"Elapsed time: {elapsed:.2f} seconds")

    for key, value in sorted(results.items()):
        print(f"{key}: {value}")

    print("=========================")


if __name__ == "__main__":
    main()