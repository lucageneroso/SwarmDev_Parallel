from fastapi import FastAPI
from app.routes import booking

app = FastAPI()

app.include_router(booking.router)