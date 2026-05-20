import React, { useState } from 'react';

const App = () => {
  const [selectedTime, setSelectedTime] = useState('');
  const [surname, setSurname] = useState('');
  const [availableTables, setAvailableTables] = useState([]);

  const timeSlots = ['18:00', '19:00', '20:00', '21:00'];

  const handleTimeChange = (event) => {
    setSelectedTime(event.target.value);
    // Simulazione di tavoli disponibili in base all'orario selezionato
    setAvailableTables(selectedTime ? ['Table 1', 'Table 2'] : []);
  };

  const handleSurnameChange = (event) => {
    setSurname(event.target.value);
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    // Logica per la prenotazione
    alert(`Prenotazione effettuata per ${surname} alle ${selectedTime}`);
  };

  return (
    <div>
      <h1>Prenotazione Tavoli</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Seleziona Fascia Oraria:
          <select value={selectedTime} onChange={handleTimeChange}>
            <option value="">--Seleziona--</option>
            {timeSlots.map((time) => (
              <option key={time} value={time}>{time}</option>
            ))}
          </select>
        </label>
        <br />
        <label>
          Cognome:
          <input type="text" value={surname} onChange={handleSurnameChange} />
        </label>
        <br />
        <button type="submit">Prenota</button>
      </form>
      {availableTables.length > 0 && (
        <div>
          <h2>Tavoli Disponibili:</h2>
          <ul>
            {availableTables.map((table) => (
              <li key={table}>{table}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default App;