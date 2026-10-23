class ChatManager:
    def __init__(self):
        self.messages = []

    def add_message(self, username, text):
        message = f"{username}: {text}"
        self.messages.append(message)
        return message

    def get_history(self):
        return self.messages.copy()