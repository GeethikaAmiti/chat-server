import socket
import threading
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

HOST = "127.0.0.1"
COORDINATOR_PORT = 5000
WAIT_TIMEOUT = 5 * 60


def request_server():
    with socket.create_connection(
        (HOST, COORDINATOR_PORT), timeout=WAIT_TIMEOUT + 10
    ) as coordinator:
        coordinator.sendall(b"ASSIGN\n")
        with coordinator.makefile("r", encoding="utf-8") as reader:
            response = reader.readline().strip()

    if response == "TIMEOUT":
        print("You waited more than five minutes. Please try again later.")
        return None

    if not response or response == "FULL":
        print("No server assignment available.")
        return None

    server_name, port = response.split("|")
    return server_name, int(port)


def release_slot(server_name):
    try:
        with socket.create_connection(
            (HOST, COORDINATOR_PORT)
        ) as coordinator:
            coordinator.sendall(f"RELEASE {server_name}\n".encode())
    except OSError:
        pass


def receive_messages(client, stop_event):
    while not stop_event.is_set():
        try:
            data = client.recv(1024)
            if not data:
                break

            print(data.decode(), end="", flush=True)

        except OSError:
            break


def main():
    username = input("Enter your username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    assignment = request_server()
    if assignment is None:
        return

    server_name, port = assignment
    stop_event = threading.Event()
    receiver = None

    try:
        with socket.create_connection((HOST, port)) as client:
            client.sendall(f"{username}\n".encode())
            print(f"Connected to {server_name}.")

            receiver = threading.Thread(
                target=receive_messages,
                args=(client, stop_event),
                daemon=False,
            )
            receiver.start()

            prompt = PromptSession()

            try:
                with patch_stdout():
                    while True:
                        message = prompt.prompt("You: ")

                        if message.lower() == "finish":
                            client.sendall(b"finish\n")

                            rating = input(
                                "Rate your session (1-5): "
                            ).strip()

                            while rating not in {"1", "2", "3", "4", "5"}:
                                rating = input(
                                    "Enter a rating from 1 to 5: "
                                ).strip()

                            client.sendall(f"{rating}\n".encode())
                            break

                        client.sendall(f"{message}\n".encode())

            except (KeyboardInterrupt, EOFError, OSError):
                pass

            finally:
                stop_event.set()
                client.shutdown(socket.SHUT_RDWR)

            receiver.join(timeout=2)
            print("Disconnected from chat.")

    except OSError as error:
        print(f"Could not connect to {server_name}: {error}")
        release_slot(server_name)


if __name__ == "__main__":
    main()
