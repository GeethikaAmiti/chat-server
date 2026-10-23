from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ClientSession:
    client_name:str
    created_at:datetime=field(default_factory=datetime.now)
    status:str="Waiting"
    server_name:str|None=None
    rating:int|None=None

class ServerSlot:
    def __init__(self,name,capacity=1):
        self.name=name
        self.capacity=capacity
        self.current_clients=[]
        self.total_clients=0
        self.ratings=[]

    @property
    def is_available(self):
        return len(self.current_clients)<self.capacity

    @property
    def average_rating(self):
        #if ratings list is empty return 0
        if not self.ratings:
            return 0
        return sum(self.ratings)/len(self.ratings)

    def assign_client(self,session):
        #if server is not available dont assign client
        if not self.is_available:
            return False
        self.current_clients.append(session)
        session.server_name=self.name
        session.status="Active"
        return True

    def finish_session(self,session,rating):
        #if the session is not even active dont finish it, return false
        if session not in self.current_clients:
            return False
        self.current_clients.remove(session)
        session.status="Completed"
        session.rating=rating
        self.ratings.append(rating)
        self.total_clients+=1
        return True

    