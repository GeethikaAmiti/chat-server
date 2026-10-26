import socket
import threading

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout


HOST = "127.0.0.1"
COORDINATOR_PORT = 5000


def request_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as coordinator:
        coordinator.connect((HOST, COORDINATOR_PORT))
        coordinator.sendall(b"ASSIGN\n")

        response = coordinator.recv(1024).decode().strip()

    if response == "FULL":
        return None

    server_name, port = response.split("|")
    return server_name, int(port)


def release_slot(server_name):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as coordinator:
            coordinator.connect((HOST, COORDINATOR_PORT))
            coordinator.sendall(f"RELEASE {server_name}\n".encode())
    except OSError:
        pass


def receive_messages(client):
    while True:
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
        print("All servers are full. Please try again later.")
        return

    server_name, port = assignment
    connected = False

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect((HOST, port))
            connected = True

            client.sendall(f"{username}\n".encode())

            print(f"Connecting to {server_name}...")

            receiver = threading.Thread(
                target=receive_messages,
                args=(client,),
                daemon=True,
            )
            receiver.start()

            prompt = PromptSession()

            try:
                with patch_stdout():
                    while True:
                        message = prompt.prompt("You: ")

                        if message.lower() == "exit":
                            break

                        client.sendall(f"{message}\n".encode())

            except (KeyboardInterrupt, EOFError, OSError):
                pass

            print("Disconnected from chat.")

    except OSError as error:
        print(f"Could not connect to {server_name}: {error}")

    finally:
        if not connected:
            release_slot(server_name)


if __name__ == "__main__":
    main()