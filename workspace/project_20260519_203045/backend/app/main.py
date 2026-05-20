from fastapi import FastAPI
from app.routes import booking, user

app = FastAPI()

app.include_router(booking.router)
app.include_router(user.router)