const express = require('express');
const sqlite3 = require('sqlite3').verbose();

const app = express();
app.use(express.json());

const db = new sqlite3.Database(':memory:');

// Create tables
const createTables = () => {
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
};

createTables();

// POST /prenotazioni
app.post('/prenotazioni', (req, res) => {
  const { nome_cliente, numero_persone, data_ora, tavolo_id } = req.body;

  // Check table capacity
  db.get('SELECT numero_posti FROM tavoli WHERE id = ?', [tavolo_id], (err, row) => {
    if (err) {
      return res.status(500).send({ error: 'Errore database' });
    }
    if (!row || numero_persone > row.numero_posti) {
      return res.status(400).send({ error: 'Numero persone eccede la capacità del tavolo' });
    }

    // Check for existing booking at the same time
    db.get('SELECT * FROM prenotazioni WHERE tavolo_id = ? AND data_ora = ?', [tavolo_id, data_ora], (err, existing) => {
      if (err) {
        return res.status(500).send({ error: 'Errore database' });
      }
      if (existing) {
        return res.status(400).send({ error: 'Prenotazione esistente nel medesimo orario' });
      }

      // Create new booking
      db.run('INSERT INTO prenotazioni (nome_cliente, numero_persone, data_ora, tavolo_id) VALUES (?, ?, ?, ?)',
        [nome_cliente, numero_persone, data_ora, tavolo_id],
        function (err) {
          if (err) {
            return res.status(500).send({ error: 'Errore database' });
          }
          res.status(201).send({ id: this.lastID });
        });
    });
  });
});

// DELETE /prenotazioni/:id
app.delete('/prenotazioni/:id', (req, res) => {
  const { id } = req.params;
  db.run('DELETE FROM prenotazioni WHERE id = ?', [id], function (err) {
    if (err) {
      return res.status(500).send({ error: 'Errore database' });
    }
    if (this.changes === 0) {
      return res.status(404).send({ error: 'Prenotazione non trovata' });
    }
    res.status(204).send();
  });
});

// GET /prenotazioni/mie
app.get('/prenotazioni/mie', (req, res) => {
  db.all('SELECT * FROM prenotazioni', [], (err, rows) => {
    if (err) {
      return res.status(500).send({ error: 'Errore database' });
    }
    res.status(200).send(rows);
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
