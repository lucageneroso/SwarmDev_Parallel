from fastapi import APIRouter, HTTPException
from app.models.movie import Movie
from app.database import SessionLocal

router = APIRouter()

@router.post("/movies/")
def create_movie(movie: Movie):
    db = SessionLocal()
    db.add(movie)
    db.commit()
    db.refresh(movie)
    db.close()
    return movie

@router.get("/movies/{movie_id}")
def read_movie(movie_id: int):
    db = SessionLocal()
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    db.close()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie