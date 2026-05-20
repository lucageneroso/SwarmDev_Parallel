from sqlalchemy.orm import Session
from app.models.booking import Booking
from app.schemas.booking import BookingCreate

def create_booking(db: Session, booking: BookingCreate):
    db_booking = Booking(**booking.dict())
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking