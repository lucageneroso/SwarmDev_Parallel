class User {
    constructor(id, role) {
        this.id = id;
        this.role = role;
    }

    canCreateOrModifyOrDelete(appointment) {
        return ['admin', 'segretario'].includes(this.role);
    }

    canViewOrRequestOrDelete(appointment) {
        return this.role === 'cliente' && appointment.clientId === this.id;
    }
}

class Appointment {
    constructor(date, time, clientId, description, status) {
        this.date = date;
        this.time = time;
        this.clientId = clientId;
        this.description = description;
        this.status = status;
    }

    isValid() {
        const dateRegex = /^\\d{4}-\\d{2}-\\d{2}$/;
        const timeRegex = /^\\d{2}:\\d{2}$/;
        const statusValues = ['confermato', 'annullato', 'completato'];

        return dateRegex.test(this.date) &&
               timeRegex.test(this.time) &&
               this.clientId != null &&
               statusValues.includes(this.status);
    }
}
