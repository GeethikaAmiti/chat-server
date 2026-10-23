import socket
import threading
from chat_manager import ChatManager

HOST = "127.0.0.1"
PORT = 5000

clients = {}
clients_lock = threading.Lock()
chat_manager=ChatManager()

def handle_client(connection, address):
    print(f"Connected by {address}")

    with connection:
        username = connection.recv(1024).decode().strip()

        if not username:
            return

        with clients_lock:
            clients[connection] = username

        #making sure new user can see chat history
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

                formatted_message=chat_manager.add_message(username,message)
                print(formatted_message)

                broadcast_message=f"{formatted_message}\n".encode()

                with clients_lock:
                    for client in clients:
                        if client!=connection:
                            try:
                                client.sendall(broadcast_message)
                            except OSError:
                                pass

        finally:
            with clients_lock:
                clients.pop(connection, None)

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