import threading

class ChatManager:
    def __init__(self):
        #store chat messages shared by all client threads.
        self.messages = []

        #prevent multiple threads from accessing the message list simultaneously while it is being read or modified.
        self.lock = threading.Lock()

    def add_message(self, username, text):
        """Add a message to the shared chat history safely."""

        message = f"{username}: {text}"

        #acquire the lock before modifying the shared list.
        with self.lock:
            self.messages.append(message)

        return message

    def get_history(self):
        """Return a safe copy of the current chat history."""

        #acquire the lock while copying the shared list.
        with self.lock:
            return self.messages.copy()
