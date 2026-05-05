'use strict';

const express = require('express');
const bodyParser = require('body-parser');
const { User, Appointment } = require('./models');

const app = express();
app.use(bodyParser.json());

// Sample data
let appointments = [];
let users = [new User('1', 'admin'), new User('2', 'segretario'), new User('3', 'cliente')];

app.post('/appointments', (req, res) => {
    const { date, time, clientId, description, status } = req.body;
    const client = users.find(user => user.id === clientId);

    if (client && client.canCreateOrModifyOrDelete()) {
        const newAppointment = new Appointment(date, time, clientId, description, status);

        if (newAppointment.isValid()) {
            appointments.push(newAppointment);
            return res.status(201).send(newAppointment);
        } else {
            return res.status(400).send('Invalid appointment data.');
        }
    } else {
        return res.status(403).send('Unauthorized.');
    }
});

app.get('/appointments', (req, res) => {
    const { clientId } = req.query;
    const client = users.find(user => user.id === clientId);

    if (client && client.canViewOrRequestOrDelete()) {
        const clientAppointments = appointments.filter(app => app.clientId === clientId);
        return res.status(200).send(clientAppointments);
    } else {
        return res.status(403).send('Unauthorized.');
    }
});

app.delete('/appointments/:id', (req, res) => {
    const { clientId } = req.body;
    const client = users.find(user => user.id === clientId);

    if (client && client.canViewOrRequestOrDelete()) {
        appointments = appointments.filter(app => app.clientId !== clientId);
        return res.status(200).send('Appointment deleted.');
    } else {
        return res.status(403).send('Unauthorized.');
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}.`);
});
