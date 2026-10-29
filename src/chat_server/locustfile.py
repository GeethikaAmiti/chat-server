import itertools
import socket
import time
from locust import User, task, between

# coordinator connection settings
HOST = "127.0.0.1"
COORDINATOR_PORT = 5000

# match the five-minute waiting period configured in Coordinator
WAIT_TIMEOUT = 10

# generate unique names for simulated clients
client_counter = itertools.count(1)

class ChatClient(User):
    """Simulate a client connecting to the TCP chat server."""

    wait_time = between(1, 2)

    def on_start(self):
        self.username = f"LocustClient_{next(client_counter)}"

    def record_result(
        self,
        name,
        started_at,
        error=None,
        response_length=0,
    ):
        """Send a measurement to Locust's statistics."""
        self.environment.events.request.fire(
            request_type="TCP",
            name=name,
            response_time=(
                time.perf_counter() - started_at
            ) * 1000,
            response_length=response_length,
            exception=error,
            context={},
        )

    @task
    def chat_session(self):
        coordinator = None
        client = None

        # 1. request a server from the coordinator.
        assignment_started = time.perf_counter()
        assignment_error = None
        assignment_response = ""

        try:
            coordinator = socket.create_connection(
                (HOST, COORDINATOR_PORT),
                timeout=WAIT_TIMEOUT + 10,
            )

            coordinator.sendall(b"ASSIGN\n")

            with coordinator.makefile(
                "r",
                encoding="utf-8",
            ) as reader:
                assignment_response = reader.readline().strip()

            if assignment_response == "TIMEOUT":
                assignment_error = RuntimeError(
                    "Client waited for 10 seconds and was marked lost."
                )
            elif not assignment_response:
                assignment_error = RuntimeError(
                    "Coordinator returned an empty response."
                )

        except (OSError, ValueError) as error:
            assignment_error = error

        finally:
            if coordinator:
                coordinator.close()

            self.record_result(
                "Coordinator assignment",
                assignment_started,
                error=assignment_error,
                response_length=len(assignment_response),
            )

        # stop if the coordinator did not assign a server
        if assignment_error:
            return

        # 2. connect to the assigned server
        session_started = time.perf_counter()
        session_error = None

        try:
            server_name, port = assignment_response.split("|")

            client = socket.create_connection(
                (HOST, int(port)),
                timeout=10,
            )
            client.settimeout(10)

            with client.makefile(
                "r",
                encoding="utf-8",
            ) as reader:

                # Send the client's username.
                client.sendall(
                    f"{self.username}\n".encode()
                )


                # receive the initial greeting
                greeting = reader.readline()

                if not greeting:
                    raise ConnectionError(
                        "Server closed the connection before greeting."
                    )

                # send a chat message, finish the session and submit a valid rating
                client.sendall(
                    f"Hello from {self.username}\n".encode()
                )
                time.sleep(2)
                client.sendall(b"finish\n")
                client.sendall(b"5\n")

                # wait for confirmation that the session finished
                while True:
                    response = reader.readline()

                    if not response:
                        raise ConnectionError(
                            "Connection closed before completion."
                        )

                    if "Session completed. Thank you!" in response:
                        break

        except (OSError, ValueError, RuntimeError) as error:
            session_error = error

        finally:
            if client:
                client.close()

            self.record_result(
                "Chat session",
                session_started,
                error=session_error,
            )