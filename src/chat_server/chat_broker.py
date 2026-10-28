import json
import socket
import threading

HOST = "127.0.0.1"
PORT = 5004

# Map each connection to its registered server name.
# Multiple connections may belong to the same server.
connections = {}

lock = threading.Lock()


def handle_server(connection):
    """Register a server connection and relay its chat messages."""
    reader = connection.makefile("r", encoding="utf-8")
    name = None

    try:
        registration_line = reader.readline()

        if not registration_line:
            return

        registration = json.loads(registration_line)
        name = registration["server"]

        with lock:
            connections[connection] = name

        for line in reader:
            message = json.loads(line)
            data = (json.dumps(message) + "\n").encode()

            # Exclude only the connection that sent this message.
            # Other child processes belonging to the same server
            # must also receive it.
            with lock:
                recipients = [
                    recipient
                    for recipient in connections
                    if recipient is not connection
                ]

                for recipient in recipients:
                    try:
                        recipient.sendall(data)

                    except OSError:
                        # Its handler will remove the connection.
                        pass

    except (OSError, ValueError, KeyError) as error:
        print(f"Broker connection error: {error}")

    finally:
        with lock:
            connections.pop(connection, None)

        reader.close()
        connection.close()

def start_broker():
    """Start the shared chat broker."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

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