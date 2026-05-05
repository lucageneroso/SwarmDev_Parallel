import models

class AppointmentService:
    def __init__(self):
        self.appointments = []

    def create_appointment(self, user: models.User, appointment: models.Appointment) -> str:
        if user.can_create_modify_delete_appointment():
            self.appointments.append(appointment)
            return 'Appointment created'
        return 'Permission denied'

    def modify_appointment(self, user: models.User, appointment_id: int, new_appointment: models.Appointment) -> str:
        if user.can_create_modify_delete_appointment() and appointment_id < len(self.appointments):
            self.appointments[appointment_id] = new_appointment
            return 'Appointment modified'
        return 'Permission denied or invalid appointment ID'

    def delete_appointment(self, user: models.User, appointment_id: int) -> str:
        if user.can_create_modify_delete_appointment() and appointment_id < len(self.appointments):
            del self.appointments[appointment_id]
            return 'Appointment deleted'
        return 'Permission denied or invalid appointment ID'

    def view_appointments(self, user: models.User) -> List[models.Appointment]:
        if user.can_view_request_delete_appointment(self.appointments):
            return [a for a in self.appointments if a.client_id == user.id or user.role in ['admin','segretario']]
        return []
