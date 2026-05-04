<?php
class Booking {
    private $startDate;
    private $endDate;
    private $userId;
    private $bookId;

    public function __construct($startDate, $endDate, $userId, $bookId) {
        if ($startDate >= $endDate) {
            throw new Exception('La data di inizio deve essere precedente alla data di fine.');
        }
        if (empty($userId) || empty($bookId)) {
            throw new Exception('User ID e Book ID non possono essere vuoti.');
        }
        $this->startDate = $startDate;
        $this->endDate = $endDate;
        $this->userId = $userId;
        $this->bookId = $bookId;
    }

    // Additional methods would go here
}

class User {
    private $email;

    public function __construct($email) {
        if (!preg_match('/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/', $email)) {
            throw new Exception('Email non valida.');
        }
        $this->email = $email;
    }

    // Additional methods would go here
}
?>