const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const bodyParser = require('body-parser');
const app = express();
const port = 3000;

app.use(bodyParser.json());

// Initialize SQLite database
timeout: 120000,
const db = new sqlite3.Database(':memory:');

// Create tables
db.serialize(() => {
  db.run(`CREATE TABLE tavoli (id INTEGER PRIMARY KEY, numero_posti INTEGER);`);
  db.run(`CREATE TABLE prenotazioni (
    id INTEGER PRIMARY KEY,
    nome_cliente TEXT,
    numero_persone INTEGER,
    data_ora TEXT,
    tavolo_id INTEGER,
    stato TEXT DEFAULT 'attiva',
    FOREIGN KEY(tavolo_id) REFERENCES tavoli(id)
  );`);
});

// POST /prenotazioni - Create reservation
app.post('/prenotazioni', (req, res) => {
  const { nome_cliente, numero_persone, data_ora, tavolo_id } = req.body;
  
  db.get(`SELECT numero_posti FROM tavoli WHERE id = ?`, [tavolo_id], (err, row) => {
    if (err) {
      return res.status(500).json({ error: 'Errore del server' });
    }
    if (!row) {
      return res.status(404).json({ error: 'Tavolo non trovato' });
    }
    if (numero_persone > row.numero_posti) {
      return res.status(400).json({ error: 'Numero di persone superiore ai posti disponibili' });
    }
    db.get(
      `SELECT * FROM prenotazioni WHERE tavolo_id = ? AND data_ora = ? AND id != ?`,
      [tavolo_id, data_ora, ''],
      (err, existing) => {
        if (err) {
          return res.status(500).json({ error: 'Errore del server' });
        }
        if (existing) {
          return res.status(400).json({ error: 'Prenotazione già esistente per la fascia oraria' });
        }
        db.run(
          `INSERT INTO prenotazioni (nome_cliente, numero_persone, data_ora, tavolo_id) VALUES (?, ?, ?, ?)`,
          [nome_cliente, numero_persone, data_ora, tavolo_id],
          function (err) {
            if (err) {
              return res.status(500).json({ error: 'Errore del server' });
            }
            res.status(201).json({ id: this.lastID });
          }
        );
      }
    );
  });
});

// DELETE /prenotazioni/:id - Delete reservation
app.delete('/prenotazioni/:id', (req, res) => {
  const { id } = req.params;
  db.run(`DELETE FROM prenotazioni WHERE id = ?`, [id], function (err) {
    if (err) {
      return res.status(500).json({ error: 'Errore del server' });
    }
    if (this.changes === 0) {
      return res.status(404).json({ error: 'Prenotazione non trovata' });
    }
    res.status(204).send();
  });
});

// GET /prenotazioni/mie - List reservations
app.get('/prenotazioni/mie', (req, res) => {
  db.all(`SELECT * FROM prenotazioni`, [], (err, rows) => {
    if (err) {
      return res.status(500).json({ error: 'Errore del server' });
    }
    res.status(200).json(rows);
  });
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
