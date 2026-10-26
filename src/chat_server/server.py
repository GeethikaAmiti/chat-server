import json
import socket
import threading
from datetime import datetime

from stats_manager import update, get_dashboard
from chat_manager import ChatManager
from archive_logger import log_event

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
        with socket.create_connection(
            (HOST, COORDINATOR_PORT)
        ) as coordinator:
            coordinator.sendall(
                f"RELEASE {server_name}\n".encode()
            )
    except OSError as error:
        print(f"Could not release slot: {error}")


def broadcast(message, exclude=None):
    with clients_lock:
        recipients = [
            client for client in clients if client is not exclude
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
    except (OSError, AttributeError) as error:
        print(f"Could not publish message: {error}")


def receive_shared_messages(connection, server_name):
    reader = connection.makefile("r", encoding="utf-8")

    try:
        for line in reader:
            event = json.loads(line)
            message = f"{event['username']}: {event['message']}"

            chat_manager.add_message(
                event["username"], event["message"]
            )
            broadcast(message)

    except (OSError, ValueError, KeyError):
        print(f"{server_name}: Chat broker connection lost.")

    finally:
        reader.close()


def print_dashboard(server_name, current_client):
    stats = get_dashboard(server_name)

    average = stats["average_rating"]
    average_text = (
        f"{average:.2f}/5" if average is not None else "N/A"
    )

    print(f"\n=== {server_name} DASHBOARD ===")
    print(f"Date and time:        {stats['time']}")
    print(f"Clients served today: {stats['served_today']}")
    print(f"Clients served month: {stats['served_month']}")
    print(f"Average rating:       {average_text}")
    print(f"Clients approached:   {stats['approached']}")
    print(f"Lost clients:         {stats['lost']}")
    print(f"Current client:       {current_client or 'None'}")
    print("==============================\n")


def handle_client(connection, address, server_name):
    username = ""
    reader = None
    entered_at = None
    message_count = 0
    rating = None

    print(f"{server_name}: Connection from {address}")

    try:
        with connection:
            reader = connection.makefile("r", encoding="utf-8")
            username = reader.readline().strip()

            # Ignore empty connections and common HTTP probes.
            if (
                not username
                or username.startswith(("HEAD ", "GET ", "POST "))
            ):
                return

            entered_at = datetime.now()

            with clients_lock:
                clients[connection] = username

            print(f"{username} joined {server_name}")
            log_event(f"{username} joined {server_name}")

            print_dashboard(server_name, username)

            connection.sendall(
                f"You are connected to {server_name}.\n".encode()
            )

            for message in chat_manager.get_history():
                connection.sendall(f"{message}\n".encode())

            for line in reader:
                message = line.strip()

                if message.lower() == "finish":
                    rating_text = reader.readline().strip()

                    try:
                        value = int(rating_text)

                        if not 1 <= value <= 5:
                            raise ValueError

                        rating = value

                    except ValueError:
                        connection.sendall(
                            b"Invalid rating. Rating must be 1-5.\n"
                        )
                        continue

                    connection.sendall(
                        b"Session completed. Thank you!\n"
                    )
                    break

                if not message:
                    continue

                message_count += 1

                log_event(
                    f"{username} on {server_name}: {message}"
                )

                chat_manager.add_message(username, message)

                broadcast(
                    f"{username}: {message}",
                    exclude=connection,
                )

                publish_message(
                    server_name, username, message
                )

    except OSError as error:
        print(f"Connection error for {username}: {error}")

    finally:
        if reader:
            reader.close()

        with clients_lock:
            clients.pop(connection, None)

        # Save statistics and log only genuine client sessions.
        if username and entered_at is not None:
            left_at = datetime.now()
            duration = (left_at - entered_at).total_seconds()

            try:
                update(
                    server_name,
                    username,
                    entered_at,
                    left_at,
                    duration,
                    message_count,
                    rating,
                )
            except (OSError, ValueError) as error:
                print(f"Could not save session statistics: {error}")

            log_event(
                f"{username} ended session on {server_name}; "
                f"duration={duration:.2f}s; "
                f"messages={message_count}; rating={rating}"
            )

            print(
                f"Session summary: {username} | "
                f"Server: {server_name} | "
                f"Duration: {duration:.2f}s | "
                f"Messages: {message_count} | Rating: {rating}"
            )

            print_dashboard(server_name, None)
            release_slot(server_name)


def start_server(name, port):
    global broker_socket

    broker_socket = socket.create_connection(
        (HOST, BROKER_PORT)
    )

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
                daemon=True,
            ).start()


if __name__ == "__main__":
    start_server("Server A", 5001)
