from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ClientSession:
    client_name: str
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "Waiting"
    server_name: str | None = None
    rating: int | None = None
    entered_at: datetime | None = None
    left_at: datetime | None = None
    message_count: int = 0
    waiting_time: float | None = None


class ServerSlot:
    def __init__(self, name, capacity=5):
        self.name = name
        self.capacity = capacity
        self.current_clients = []
        self.total_clients = 0
        self.ratings = []
        self.completed_at = []

    @property
    def is_available(self):
        return len(self.current_clients) < self.capacity

    @property
    def average_rating(self):
        if not self.ratings:
            return 0
        return sum(self.ratings) / len(self.ratings)

    def assign_client(self, session):
        if not self.is_available:
            return False

        self.current_clients.append(session)
        session.server_name = self.name
        session.status = "Active"
        session.entered_at = datetime.now()
        session.waiting_time = (
            session.entered_at - session.created_at
        ).total_seconds()
        return True

    def finish_session(self, session, rating):
        if session not in self.current_clients:
            return False

        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError("Rating must be an integer from 1 to 5.")

        self.current_clients.remove(session)
        session.status = "Completed"
        session.left_at = datetime.now()
        session.rating = rating
        self.ratings.append(rating)
        self.completed_at.append(session.left_at)
        self.total_clients += 1
        return True