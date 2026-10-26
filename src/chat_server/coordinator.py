import socket
import threading

HOST = "127.0.0.1"
PORT = 5000
CAPACITY = 5

servers = {
    "Server A": {"port": 5001, "active": 0},
    "Server B": {"port": 5002, "active": 0},
    "Server C": {"port": 5003, "active": 0},
}

servers_lock = threading.Lock()


def handle_request(connection):
    with connection:
        request = connection.recv(1024).decode().strip()

        if request == "ASSIGN":
            with servers_lock:
                for name, details in servers.items():
                    if details["active"] < CAPACITY:
                        details["active"] += 1

                        response = (
                            f"{name}|{details['port']}\n"
                        )
                        connection.sendall(response.encode())

                        print(
                            f"Assigned client to {name}. "
                            f"Active clients: {details['active']}"
                        )
                        return

                connection.sendall(b"FULL\n")

        elif request.startswith("RELEASE "):
            name = request.removeprefix("RELEASE ").strip()

            with servers_lock:
                if name in servers and servers[name]["active"] > 0:
                    servers[name]["active"] -= 1

                    print(
                        f"Released slot on {name}. "
                        f"Active clients: {servers[name]['active']}"
                    )

def start_coordinator():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()

        print(f"Coordinator listening on {HOST}:{PORT}")

        while True:
            connection, address = server.accept()

            thread = threading.Thread(
                target=handle_request,
                args=(connection,),
                daemon=True,
            )
            thread.start()


if __name__ == "__main__":
    start_coordinator()