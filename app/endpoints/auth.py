from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # ← ВСЁ ЗДЕСЬ!
from pydantic import BaseModel, EmailStr
from typing import Optional
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/api/auth")
security = HTTPBearer()

SECRET_KEY = "secret_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1
REFRESH_TOKEN_EXPIRE_DAYS = 7
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

def validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 8 символов")
    return True

def get_password_hash(password: str):
    validate_password(password)
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(user: User):
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user.user_id),  # ← user_id, не email!
        "role": user.role.value,
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user: User):
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user.user_id),  # ← user_id, не email!
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def decode_token(token: str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload

@router.post("/register", response_model=TokenResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole.user  # по умолчанию user
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(new_user)
    refresh_token = create_refresh_token(new_user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/login", response_model=TokenResponse)
def login(user_data: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user_data.email).first()
    if not db_user or not verify_password(user_data.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token(db_user)
    refresh_token = create_refresh_token(db_user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.value
    }

@router.post("/refresh-token", response_model=TokenResponse)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.user_id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        new_access_token = create_access_token(user)
        new_refresh_token = create_refresh_token(user)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


__all__ = ["router", "get_current_user"]