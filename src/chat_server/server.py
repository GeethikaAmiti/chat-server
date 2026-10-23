import socket
HOST="127.0.0.1"
PORT=5000
with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as server:
    server.bind((HOST,PORT))
    server.listen()
    print(f"Server listening on {HOST}:{PORT}")
    while True:
        connection,address=server.accept()
        print(f"Connected by {address}")
        with connection:
                data=connection.recv(1024)
                print(f"Client says: {data.decode()}")
                connection.sendall(b"Hello from the server sweetss!")


