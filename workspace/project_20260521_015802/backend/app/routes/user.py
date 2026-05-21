from fastapi import APIRouter, HTTPException
from app.models.user import User
from app.database import SessionLocal
from passlib.context import CryptContext

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/users/")
def create_user(user: User):
    db = SessionLocal()
    user.hashed_password = pwd_context.hash(user.hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user

@router.get("/users/{user_id}")
def read_user(user_id: int):
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user