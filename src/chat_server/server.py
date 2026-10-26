import socket
import threading

from chat_manager import ChatManager

HOST = "127.0.0.1"
COORDINATOR_PORT = 5000

clients = {}
clients_lock = threading.Lock()
chat_manager = ChatManager()


def release_slot(server_name):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as coordinator:
            coordinator.connect((HOST, COORDINATOR_PORT))
            coordinator.sendall(f"RELEASE {server_name}\n".encode())
    except OSError as error:
        print(f"Could not release slot for {server_name}: {error}")


def handle_client(connection, address, server_name):
    username = ""
    reader = None

    print(f"{server_name}: Connection from {address}")

    try:
        with connection:
            reader = connection.makefile("r", encoding="utf-8")
            username = reader.readline().strip()

            if not username:
                return

            with clients_lock:
                clients[connection] = username

            connection.sendall(
                f"You are connected to {server_name}.\n".encode()
            )

            for message in chat_manager.get_history():
                connection.sendall(f"{message}\n".encode())

            print(f"{username} joined {server_name}")

            while True:
                message = reader.readline()

                if not message:
                    break

                message = message.strip()

                if not message:
                    continue

                formatted_message = chat_manager.add_message(
                    username, message
                )
                print(formatted_message)

                with clients_lock:
                    for client in list(clients):
                        if client is connection:
                            continue

                        try:
                            client.sendall(
                                f"{formatted_message}\n".encode()
                            )
                        except OSError:
                            pass

    except OSError as error:
        print(f"Connection error for {username}: {error}")

    finally:
        if reader is not None:
            reader.close()

        with clients_lock:
            clients.pop(connection, None)

        if username:
            print(f"{username} disconnected from {server_name}")

        release_slot(server_name)


def start_server(name, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, port))
        server.listen()

        print(f"{name} listening on {HOST}:{port}")

        while True:
            connection, address = server.accept()

            thread = threading.Thread(
                target=handle_client,
                args=(connection, address, name),
            )
            thread.start()


if __name__ == "__main__":
    start_server("Server A", 5001)