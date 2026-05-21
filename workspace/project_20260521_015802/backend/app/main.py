from fastapi import FastAPI
from app.routes import movie, user

app = FastAPI()

app.include_router(movie.router)
app.include_router(user.router)