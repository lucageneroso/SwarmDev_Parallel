from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.booking import BookingCreate, BookingResponse
from app.services.booking_service import create_booking
from app.database import get_db

router = APIRouter()

@router.post("/bookings/", response_model=BookingResponse)
def create_booking_route(booking: BookingCreate, db: Session = Depends(get_db)):
    return create_booking(db=db, booking=booking)