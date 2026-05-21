import React from 'react';
import MovieList from './components/MovieList';
import SeatSelection from './components/SeatSelection';
import Payment from './components/Payment';

function App() {
  return (
    <div>
      <h1>Movie Booking App</h1>
      <MovieList />
      <SeatSelection />
      <Payment />
    </div>
  );
}

export default App;