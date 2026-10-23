import socket
import threading

HOST = "127.0.0.1"
PORT = 5000


def receive_messages(client):
    while True:
        try:
            data = client.recv(1024)

            if not data:
                break
            #better formatting
            print(data.decode(), end="", flush=True)
        except OSError:
            break


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
    client.connect((HOST, PORT))
    print("Connected to the server!")

    username = input("Enter your username: ").strip()
    client.sendall(f"{username}\n".encode())

    receiver = threading.Thread(
        target=receive_messages,
        args=(client,),
        daemon=True,
    )
    receiver.start()

    try:
        while True:
            message = input("You: ")

            if message.lower() == "exit":
                break

            client.sendall(f"{message}\n".encode())

    except (KeyboardInterrupt, OSError):
        pass

    print("Disconnected from chat.")