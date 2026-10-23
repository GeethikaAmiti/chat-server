import socket
import threading

HOST = "127.0.0.1"
PORT = 5000

clients = {}
clients_lock = threading.Lock()

def handle_client(connection, address):
    print(f"Connected by {address}")

    with connection:
        username = connection.recv(1024).decode().strip()

        if not username:
            return

        with clients_lock:
            clients[connection] = username

        print(f"{username} joined the chat")

        try:
            while True:
                data = connection.recv(1024)

                if not data:
                    break

                message = data.decode()
                print(f"{username}: {message}")

                broadcast_message=f"{username}: {message}\n".encode()
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