import socket
import threading
import time
import select
from collections import deque
from datetime import datetime

from chat_manager import ChatManager
from models import ClientSession, ServerSlot

HOST = "127.0.0.1"
PORT = 5000

clients = {}
clients_lock = threading.Lock()
chat_manager = ChatManager()

servers = [
    ServerSlot("Server A", capacity=5),
    ServerSlot("Server B", capacity=5),
    ServerSlot("Server C", capacity=5),
]

sessions = {}
all_sessions = []
waiting_queue = deque()
queue_condition = threading.Condition(clients_lock)
WAIT_TIMEOUT = 5 * 60


def remove_from_queue(connection):
    for entry in list(waiting_queue):
        if entry[0] is connection:
            waiting_queue.remove(entry)
            break


def client_disconnected(connection):
    try:
        readable, _, _ = select.select([connection], [], [], 0)

        if readable:
            return connection.recv(1, socket.MSG_PEEK) == b""

    except OSError:
        return True

    return False


def handle_client(connection, address):
    print(f"Connected by {address}")
    username = ""

    with connection:
        try:
            username = connection.recv(1024).decode().strip()

            if not username:
                return

            session = ClientSession(username)

            #Keep a record of every client session, including lost clients.
            with queue_condition:
                all_sessions.append(session)

            wait_started = time.monotonic()
            registered = False
            disconnected = False

            with queue_condition:
                waiting_queue.append(
                    (connection, session, wait_started)
                )

                while True:
                    if client_disconnected(connection):
                        remove_from_queue(connection)
                        session.status = "Disconnected"
                        disconnected = True
                        queue_condition.notify_all()
                        break

                    #Only the first client in the queue can claim a slot.
                    if (
                        waiting_queue
                        and waiting_queue[0][0] is connection
                    ):
                        assigned_server = next(
                            (
                                slot for slot in servers
                                if slot.is_available
                            ),
                            None,
                        )

                        if (
                            assigned_server is not None
                            and assigned_server.assign_client(session)
                        ):
                            waiting_queue.popleft()
                            clients[connection] = username
                            sessions[connection] = session
                            registered = True

                            queue_condition.notify_all()
                            break

                    remaining = WAIT_TIMEOUT - (
                        time.monotonic() - wait_started
                    )

                    if remaining <= 0:
                        remove_from_queue(connection)
                        session.status = "Lost"
                        queue_condition.notify_all()
                        break

                    queue_condition.wait(
                        timeout=min(remaining, 1.0)
                    )

            if not registered:
                if not disconnected:
                    try:
                        connection.sendall(
                            "Waited more than 5 minutes. "
                            "Please try again later.\n".encode()
                        )
                    except OSError:
                        pass

                return

            connection.sendall(
                f"You are connected to {session.server_name}.\n".encode()
            )

            # Send previous chat messages to the new user.
            for message in chat_manager.get_history():
                connection.sendall(f"{message}\n".encode())

            print(f"{username} joined the chat")

            while True:
                data = connection.recv(1024)

                if not data:
                    break

                message = data.decode().strip()

                if not message:
                    continue

                #Count messages sent by this client.
                session.message_count += 1

                formatted_message = chat_manager.add_message(
                    username, message
                )
                print(formatted_message)

                broadcast_message = f"{formatted_message}\n".encode()

                with clients_lock:
                    for client in clients:
                        if client != connection:
                            try:
                                client.sendall(broadcast_message)
                            except OSError:
                                pass

        finally:
            with queue_condition:
                remove_from_queue(connection)

                clients.pop(connection, None)
                active_session = sessions.pop(connection, None)

                #Record the exit time, regardless of how the session ended.
                if "session" in locals() and session.left_at is None:
                    session.left_at = datetime.now()

                if active_session is not None:
                    for server_slot in servers:
                        if active_session in server_slot.current_clients:
                            server_slot.current_clients.remove(active_session)

                            # The client occupied a server, so count it as served.
                            server_slot.total_clients += 1
                            server_slot.completed_at.append(
                                active_session.left_at
                            )

                            active_session.status = "Disconnected"
                            break

                queue_condition.notify_all()

            if username:
                print(f"{username} disconnected")

                print(f"Session summary: {session.client_name} |")
                print(f"Status: {session.status} |")
                print(f"Messages: {session.message_count} |")
                print(f"Server: {session.server_name} |")
                print(f"Waiting time: {session.waiting_time} seconds |")
                print(f"Entered: {session.entered_at} |")
                print(f"Left: {session.left_at}")


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.bind((HOST, PORT))
    server.listen()

    print(f"Server listening on {HOST}:{PORT}")

    while True:
        connection, address = server.accept()

        thread = threading.Thread(
            target=handle_client,
            args=(connection, address),
        )
        thread.start()