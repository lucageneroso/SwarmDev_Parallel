from fastapi import APIRouter

router = APIRouter()

@router.post("/book")
async def create_booking(item: dict):
    return {"message": "Booking created", "item": item}