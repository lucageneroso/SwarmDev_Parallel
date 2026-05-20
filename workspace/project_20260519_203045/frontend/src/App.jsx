import React from 'react';
import { Route, Switch } from 'react-router-dom';
import Home from './components/Home';
import BookingForm from './components/BookingForm';
import Dashboard from './components/Dashboard';
import AdminPanel from './components/AdminPanel';
import Login from './components/Login';
import Register from './components/Register';

const App = () => {
  return (
    <Switch>
      <Route path="/" exact component={Home} />
      <Route path="/booking" component={BookingForm} />
      <Route path="/dashboard" component={Dashboard} />
      <Route path="/admin" component={AdminPanel} />
      <Route path="/login" component={Login} />
      <Route path="/register" component={Register} />
    </Switch>
  );
};

export default App;