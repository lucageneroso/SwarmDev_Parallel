import React, { useState } from 'react';

const SeatSelection = () => {
  const [selectedSeats, setSelectedSeats] = useState([]);

  const toggleSeat = (seat) => {
    setSelectedSeats(prevSeats =>
      prevSeats.includes(seat) ? prevSeats.filter(s => s !== seat) : [...prevSeats, seat]
    );
  };

  const seats = Array.from({ length: 10 }, (_, i) => i + 1);

  return (
    <div>
      <h2>Select Seats</h2>
      <div>
        {seats.map(seat => (
          <button
            key={seat}
            onClick={() => toggleSeat(seat)}
            style={{ backgroundColor: selectedSeats.includes(seat) ? 'green' : 'gray' }}
          >
            {seat}
          </button>
        ))}
      </div>
    </div>
  );
};

export default SeatSelection;