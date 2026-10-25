import socket
import threading
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


def handle_client(connection, address):
    print(f"Connected by {address}")

    with connection:
        username = connection.recv(1024).decode().strip()

        if not username:
            return

        session = ClientSession(username)

        with clients_lock:
            assigned_server = None

            for server_slot in servers:
                if server_slot.assign_client(session):
                    assigned_server = server_slot
                    break

            if assigned_server is not None:
                clients[connection] = username
                sessions[connection] = session

        if assigned_server is None:
            connection.sendall(
                "All servers are currently full. Please try again later.\n".encode()
            )
            return

        connection.sendall(
            f"You are connected to {session.server_name}.\n".encode()
        )

        # Send previous chat messages to the new user.
        for message in chat_manager.get_history():
            connection.sendall(f"{message}\n".encode())

        print(f"{username} joined the chat")

        try:
            while True:
                data = connection.recv(1024)

                if not data:
                    break

                message = data.decode().strip()

                if not message:
                    continue

                formatted_message = chat_manager.add_message(username, message)
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
            with clients_lock:
                clients.pop(connection, None)
                session = sessions.pop(connection, None)

                if session is not None:
                    for server_slot in servers:
                        if session in server_slot.current_clients:
                            server_slot.current_clients.remove(session)
                            session.status = "Disconnected"
                            break

            print(f"{username} disconnected")


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
