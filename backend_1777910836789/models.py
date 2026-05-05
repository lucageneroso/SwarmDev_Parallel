from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import re

class User(ABC):
    def __init__(self, user_id: int, role: str):
        self.id = user_id
        self.role = role

    @abstractmethod
    def can_create_modify_delete_appointment(self) -> bool:
        pass

    @abstractmethod
    def can_view_request_delete_appointment(self, appointment) -> bool:
        pass

class Admin(User):
    def can_create_modify_delete_appointment(self) -> bool:
        return True

    def can_view_request_delete_appointment(self, appointment) -> bool:
        return True

class Segretario(User):
    def can_create_modify_delete_appointment(self) -> bool:
        return True

    def can_view_request_delete_appointment(self, appointment) -> bool:
        return True

class Cliente(User):
    def can_create_modify_delete_appointment(self) -> bool:
        return False

    def can_view_request_delete_appointment(self, appointment) -> bool:
        return appointment.client_id == self.id

@dataclass
class Appointment:
    date: str
    time: str
    client_id: int
    description: Optional[str] = None
    status: str = 'confermato'

    def __post_init__(self):
        if not re.match(r'^\\d{4}-\\d{2}-\\d{2}$', self.date):
            raise ValueError('Date must be in the format YYYY-MM-DD')
        if not re.match(r'^\\d{2}:\\d{2}$', self.time):
            raise ValueError('Time must be in the format HH:MM')
        if self.status not in ['confermato', 'annullato', 'completato']:
            raise ValueError('Status must be one of: confermato, annullato, completato')
