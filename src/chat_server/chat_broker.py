import json
import socket
import threading

HOST = "127.0.0.1"
PORT = 5004

servers = {}
lock = threading.Lock()


def handle_server(connection):
    reader = connection.makefile("r", encoding="utf-8")
    name = None

    try:
        registration = json.loads(reader.readline())
        name = registration["server"]

        with lock:
            servers[name] = connection

        print(f"{name} registered with chat broker.")

        for line in reader:
            message = json.loads(line)

            with lock:
                recipients = [
                    sock for server_name, sock in servers.items()
                    if server_name != name
                ]

            data = (json.dumps(message) + "\n").encode()

            for recipient in recipients:
                try:
                    recipient.sendall(data)
                except OSError:
                    pass

    except (OSError, ValueError, KeyError):
        pass

    finally:
        with lock:
            if name and servers.get(name) is connection:
                del servers[name]

        reader.close()
        connection.close()


def start_broker():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()

        print(f"Chat broker listening on {HOST}:{PORT}")

        while True:
            connection, _ = server.accept()
            threading.Thread(
                target=handle_server,
                args=(connection,),
                daemon=True,
            ).start()


if __name__ == "__main__":
    start_broker()