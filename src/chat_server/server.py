import socket
import threading

HOST = "127.0.0.1"
PORT = 5000


def handle_client(connection, address):
    print(f"Connected by {address}")

    with connection:
        while True:
            data = connection.recv(1024)

            if not data:
                break

            message = data.decode()
            print(f"Client says: {message}")

            connection.sendall(b"Hello from the server!")

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