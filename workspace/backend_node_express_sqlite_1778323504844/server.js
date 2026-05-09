const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const app = express();

app.use(express.json());

const db = new sqlite3.Database(':memory:');

db.serialize(() => {
  db.run(`CREATE TABLE tavoli (
    id INTEGER PRIMARY KEY,
    numero_posti INTEGER
  )`);

  db.run(`CREATE TABLE prenotazioni (
    id INTEGER PRIMARY KEY,
    nome_cliente TEXT,
    numero_persone INTEGER,
    data_ora TEXT,
    tavolo_id INTEGER,
    stato TEXT DEFAULT 'attiva',
    FOREIGN KEY (tavolo_id) REFERENCES tavoli(id)
  )`);
});

app.post('/prenotazioni', (req, res) => {
  const { nome_cliente, numero_persone, data_ora, tavolo_id } = req.body;
  db.get('SELECT numero_posti FROM tavoli WHERE id = ?', [tavolo_id], (err, row) => {
    if (err) { res.status(400).send('Errore nel database'); return; }
    if (!row) { res.status(404).send('Tavolo non trovato'); return; }
    if (numero_persone > row.numero_posti) { res.status(400).send('Numero di persone superiore ai posti disponibili'); return; }

    db.all('SELECT * FROM prenotazioni WHERE tavolo_id = ? AND data_ora = ?', [tavolo_id, data_ora], (err, rows) => {
      if (err) { res.status(400).send('Errore nel database'); return; }
      if (rows.length > 0) { res.status(400).send('Prenotazione già esistente per questo orario'); return; }

      db.run('INSERT INTO prenotazioni (nome_cliente, numero_persone, data_ora, tavolo_id, stato) VALUES (?, ?, ?, ?, ?)',
        [nome_cliente, numero_persone, data_ora, tavolo_id, 'attiva'],
        function(err) {
          if (err) { res.status(400).send('Errore nel database'); return; }
          res.status(201).send({ id: this.lastID });
        });
    });
  });
});

app.delete('/prenotazioni/:id', (req, res) => {
  const { id } = req.params;
  db.run('DELETE FROM prenotazioni WHERE id = ?', [id], function(err) {
    if (err) { res.status(400).send('Errore nel database'); return; }
    if (this.changes === 0) { res.status(404).send('Prenotazione non trovata'); return; }
    res.status(200).send('Prenotazione cancellata');
  });
});

app.get('/prenotazioni/mie', (req, res) => {
  db.all('SELECT * FROM prenotazioni', [], (err, rows) => {
    if (err) { res.status(400).send('Errore nel database'); return; }
    res.status(200).json(rows);
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
