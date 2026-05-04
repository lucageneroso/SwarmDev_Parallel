from appointment_system import User, Appointment

# Sample instances to demonstrate usage
admin_user = User(user_id=1, role='admin')
client_user = User(user_id=2, role='cliente')

appt = Appointment(appointment_id=1001, date='2023-05-04', time='09:00', client_id=2, description='Cambio olio', status='confermato')

# Check permissions and validations
assert admin_user.can_create_or_modify_or_delete(appt) == True
assert client_user.can_view_or_request_or_delete(appt) == True
assert appt.is_valid_status() == True
assert appt.has_valid_client() == True
assert appt.has_valid_date() == True
assert appt.has_valid_time() == True
