import json
import os
import signal
import socket
import threading
from datetime import datetime

from stats_manager import update, get_dashboard
from chat_manager import ChatManager
from archive_logger import log_event

HOST = "127.0.0.1"
COORDINATOR_PORT = 5000
BROKER_PORT = 5004

# Track connected clients and protect shared data between threads.
clients = {}
clients_lock = threading.Lock()

broker_lock = threading.Lock()
broker_socket = None

chat_manager = ChatManager()

def release_slot(server_name):
    """Notify the coordinator that this server is available again."""
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
    """Send a message to all connected clients except the sender."""
    with clients_lock:
        recipients = [
            client for client in clients
            if client is not exclude
        ]

    for client in recipients:
        try:
            client.sendall(f"{message}\n".encode())

        except OSError:
            # Ignore clients that have disconnected unexpectedly.
            pass

def publish_message(server_name, username, message):
    """Publish a chat message to the shared chat broker."""
    event = json.dumps({
        "server": server_name,
        "username": username,
        "message": message,
    }) + "\n"

    try:
        with broker_lock:
            if broker_socket is not None:
                broker_socket.sendall(event.encode())

    except OSError as error:
        print(f"Could not publish message: {error}")


def receive_shared_messages(connection, server_name):
    """Receive messages from the broker and broadcast them locally."""
    reader = connection.makefile("r", encoding="utf-8")

    try:
        for line in reader:
            event = json.loads(line)

            username = event["username"]
            message = event["message"]

            # Update this process's copy of the chat history.
            chat_manager.add_message(username, message)

            # Notify clients connected to this process.
            broadcast(f"{username}: {message}")

    except (OSError, ValueError, KeyError) as error:
        print(
            f"{server_name}: Chat broker connection lost: {error}"
        )

    finally:
        reader.close()

def connect_to_broker(server_name):
    """Create a broker connection for this process."""
    global broker_socket
    global broker_lock

    # Close this process's copy of an inherited broker socket, if any.
    # Closing the child's copy does not close the parent's socket.
    if broker_socket is not None:
        try:
            broker_socket.close()
        except OSError:
            pass

    # Create a fresh lock and connection for this process.
    broker_lock = threading.Lock()

    broker_socket = socket.create_connection(
        (HOST, BROKER_PORT)
    )

    registration = json.dumps({
        "server": server_name
    }) + "\n"

    broker_socket.sendall(registration.encode())

    # Each process needs its own receiver thread.
    threading.Thread(
        target=receive_shared_messages,
        args=(broker_socket, server_name),
        daemon=True,
    ).start()

def print_dashboard(server_name, current_client):
    """Display the server's current statistics and active client."""
    stats = get_dashboard(server_name)

    average = stats["average_rating"]

    average_text = (
        f"{average:.2f}/5"
        if average is not None
        else "N/A"
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
    """Manage one client's chat session from connection to disconnection."""
    username = ""
    reader = None
    entered_at = None
    message_count = 0
    rating = None

    print(f"\n[CONNECT] {server_name} | Client connected")
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

            print(f"[SESSION] {server_name} | Client: {username} | Started")
            log_event(f"{username} joined {server_name}")

            print_dashboard(server_name, username)

            connection.sendall(
                f"You are connected to {server_name}.\n".encode()
            )

            # Send the history available in this process.
            for message in chat_manager.get_history():
                connection.sendall(f"{message}\n".encode())

            # Process messages until the client finishes the session.
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

                # Update local history and notify local clients.
                chat_manager.add_message(username, message)

                broadcast(
                    f"{username}: {message}",
                    exclude=connection,
                )

                # Share the message with other server processes.
                publish_message(
                    server_name,
                    username,
                    message,
                )

    except OSError as error:
        print(f"Connection error for {username}: {error}")

    finally:
        if reader:
            reader.close()

        with clients_lock:
            clients.pop(connection, None)

        # Save statistics only for genuine client sessions.
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
                f"Entered at: "
                f"{entered_at.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Left at: "
                f"{left_at.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Duration: {duration:.2f}s | "
                f"Messages: {message_count} | Rating: {rating}"
            )

            print_dashboard(server_name, None)
            release_slot(server_name)

def restore_child_history(history):
    """Create fresh child-process state and restore chat history."""
    global clients
    global clients_lock
    global broker_lock
    global chat_manager

    # Do not reuse inherited thread locks in the child process.
    clients = {}
    clients_lock = threading.Lock()
    broker_lock = threading.Lock()

    # Create a fresh ChatManager rather than reusing its inherited lock.
    chat_manager = ChatManager()

    # History entries are formatted as 'username: message'.
    for entry in history:
        if ": " in entry:
            username, message = entry.split(": ", 1)
            chat_manager.add_message(username, message)

def reap_children(signum, frame):
    """Collect completed child processes without blocking."""
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)

            if pid == 0:
                break

        except ChildProcessError:
            break

def start_server(name, port):
    """Start a server that supports iterative, threading, or forking mode."""
    global broker_socket

    mode = os.getenv("CHAT_MODE", "threading")

    if mode not in ("iterative", "threading", "forking"):
        raise ValueError(
            "CHAT_MODE must be iterative, threading, or forking."
        )

    # Reap completed children in forking mode.
    if mode == "forking":
        signal.signal(signal.SIGCHLD, reap_children)

    # The parent process maintains its broker connection and chat history.
    connect_to_broker(name)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )
        server.bind((HOST, port))
        server.listen()

        print(f"{name} listening on {HOST}:{port}")

        while True:
            connection, address = server.accept()

            if mode == "threading":
                threading.Thread(
                    target=handle_client,
                    args=(connection, address, name),
                    daemon=True,
                ).start()

            elif mode == "iterative":
                handle_client(connection, address, name)

            elif mode == "forking":
                # Capture the latest history before creating the child.
                history = chat_manager.get_history()

                try:
                    pid = os.fork()

                except OSError as error:
                    connection.close()
                    print(
                        f"Could not fork for client {address}: {error}"
                    )
                    continue

                if pid == 0:
                    # Child process: handle this client independently.
                    server.close()

                    try:
                        restore_child_history(history)

                        # Give this child its own broker connection.
                        connect_to_broker(name)

                        handle_client(
                            connection,
                            address,
                            name,
                        )

                    except Exception as error:
                        print(
                            f"Child process error for {address}: {error}"
                        )

                    finally:
                        connection.close()

                        if broker_socket is not None:
                            try:
                                broker_socket.shutdown(
                                    socket.SHUT_RDWR
                                )
                            except OSError:
                                pass

                            try:
                                broker_socket.close()
                            except OSError:
                                pass

                        # Exit without running the parent's Python cleanup.
                        os._exit(0)

                else:
                    # Parent process keeps accepting new clients.
                    connection.close()

if __name__ == "__main__":
    start_server("Server A", 5001)