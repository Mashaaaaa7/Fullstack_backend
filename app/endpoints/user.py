from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.auth import get_password_hash, verify_password, create_access_token
from app.models import User
from app.database import SessionLocal

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register(user: UserCreate):
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "success": True,
            "access_token": create_access_token({"sub": str(new_user.user_id)}),
            "token_type": "bearer"
        }
    finally:
        db.close()

@router.post("/login")
def login(user: UserCreate):
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.email == user.email).first()

        if not db_user or not verify_password(user.password, db_user.hashed_password):
            raise HTTPException(status_code=400, detail="Invalid credentials")

        return {
            "success": True,
            "access_token": create_access_token({"sub": str(db_user.user_id)}),
            "token_type": "bearer"
        }
    finally:
        db.close()