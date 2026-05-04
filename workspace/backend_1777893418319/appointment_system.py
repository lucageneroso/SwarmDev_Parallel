class User:
    def __init__(self, user_id, role):
        self.id = user_id
        self.role = role

    def can_create_or_modify_or_delete(self, appointment):
        return self.role in ['admin', 'segretario']

    def can_view_or_request_or_delete(self, appointment):
        return self.role == 'cliente' and appointment.client_id == self.id


class Appointment:
    def __init__(self, appointment_id, date, time, client_id, description, status):
        self.id = appointment_id
        self.date = date
        self.time = time
        self.client_id = client_id
        self.description = description
        self.status = status

    def is_valid_status(self):
        return self.status in ['confermato', 'annullato', 'completato']

    def has_valid_client(self):
        return bool(self.client_id)

    def has_valid_date(self):
        import re
        return re.match(r'^\\d{4}-\\d{2}-\\d{2}$', self.date) is not None

    def has_valid_time(self):
        import re
        return re.match(r'^\\d{2}:\\d{2}$', self.time) is not None
