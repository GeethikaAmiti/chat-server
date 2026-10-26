import json
import socket
import threading

from chat_manager import ChatManager

HOST = "127.0.0.1"
COORDINATOR_PORT = 5000
BROKER_PORT = 5004

clients = {}
clients_lock = threading.Lock()
broker_lock = threading.Lock()
broker_socket = None
chat_manager = ChatManager()


def release_slot(server_name):
    try:
        with socket.create_connection((HOST, COORDINATOR_PORT)) as coordinator:
            coordinator.sendall(f"RELEASE {server_name}\n".encode())
    except OSError as error:
        print(f"Could not release slot: {error}")


def broadcast(message, exclude=None):
    with clients_lock:
        recipients = [
            client for client in clients
            if client is not exclude
        ]

    for client in recipients:
        try:
            client.sendall(f"{message}\n".encode())
        except OSError:
            pass


def publish_message(server_name, username, message):
    event = json.dumps({
        "server": server_name,
        "username": username,
        "message": message,
    }) + "\n"

    try:
        with broker_lock:
            broker_socket.sendall(event.encode())
    except OSError as error:
        print(f"Could not publish chat message: {error}")


def receive_shared_messages(connection, server_name):
    reader = connection.makefile("r", encoding="utf-8")

    try:
        for line in reader:
            event = json.loads(line)
            message = f"{event['username']}: {event['message']}"
            chat_manager.add_message(event["username"], event["message"])
            broadcast(message)

    except (OSError, ValueError, KeyError):
        print(f"{server_name}: Chat broker connection lost.")

    finally:
        reader.close()


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

            for line in reader:
                message = line.strip()

                if not message:
                    continue

                chat_manager.add_message(username, message)
                formatted = f"{username}: {message}"

                print(formatted)

                # Deliver locally, then send to other servers.
                broadcast(formatted, exclude=connection)
                publish_message(server_name, username, message)

    except OSError as error:
        print(f"Connection error: {error}")

    finally:
        if reader:
            reader.close()

        with clients_lock:
            clients.pop(connection, None)

        if username:
            print(f"{username} disconnected from {server_name}")

        release_slot(server_name)


def start_server(name, port):
    global broker_socket

    broker_socket = socket.create_connection((HOST, BROKER_PORT))
    broker_socket.sendall(
        (json.dumps({"server": name}) + "\n").encode()
    )

    threading.Thread(
        target=receive_shared_messages,
        args=(broker_socket, name),
        daemon=True,
    ).start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, port))
        server.listen()

        print(f"{name} listening on {HOST}:{port}")

        while True:
            connection, address = server.accept()
            threading.Thread(
                target=handle_client,
                args=(connection, address, name),
            ).start()


if __name__ == "__main__":
    start_server("Server A", 5001)