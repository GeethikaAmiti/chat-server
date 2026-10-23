import socket
HOST="127.0.0.1"
PORT=5000
with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as client:
    client.connect((HOST,PORT))
    message="Hello from the clienttt!"
    client.sendall(message.encode())
    response=client.recv(1024)
    print(f"Server says {response.decode()}")