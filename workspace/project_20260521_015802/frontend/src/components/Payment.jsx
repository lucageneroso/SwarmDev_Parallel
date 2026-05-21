import React from 'react';

const Payment = () => {
  const handlePayment = () => {
    alert('Payment completed!');
  };

  return (
    <div>
      <h2>Payment</h2>
      <button onClick={handlePayment}>Pay Now</button>
    </div>
  );
};

export default Payment;