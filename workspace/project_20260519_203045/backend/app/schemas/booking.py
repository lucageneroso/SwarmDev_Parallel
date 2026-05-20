from pydantic import BaseModel
from datetime import datetime

class BookingCreate(BaseModel):
    user_id: int
    start_time: datetime
    end_time: datetime
    description: str

class BookingResponse(BookingCreate):
    id: int

    class Config:
        orm_mode = True