from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, RefreshToken
import uuid

router = APIRouter()
security = HTTPBearer()

SECRET_KEY = "secret_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# --- Pydantic схемы ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

# --- Вспомогательные функции ---
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
        "sub": str(user.user_id),
        "role": user.role.value,
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user: User, jti: str):
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user.user_id),
        "jti": jti,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/register", response_model=TokenResponse)
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole.user
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(new_user)
    jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(new_user, jti)

    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh = RefreshToken(
        id=jti,
        user_id=new_user.user_id,
        expires_at=expires_at,
        device_info=request.headers.get("user-agent")
    )
    db.add(db_refresh)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/login", response_model=TokenResponse)
def login(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user_data.email).first()
    if not db_user or not verify_password(user_data.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token(db_user)
    jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(db_user, jti)

    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh = RefreshToken(
        id=jti,
        user_id=db_user.user_id,
        expires_at=expires_at,
        device_info=request.headers.get("user-agent")
    )
    db.add(db_refresh)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    refresh_token = data.refresh_token
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        user_id = int(payload.get("sub"))
        if not jti or not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    db_refresh = db.query(RefreshToken).filter(RefreshToken.id == jti).first()
    if not db_refresh:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    if db_refresh.revoked:
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    if db_refresh.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expired")
    if db_refresh.user_id != user_id:
        raise HTTPException(status_code=401, detail="Token user mismatch")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Ротация токена
    db_refresh.revoked = True
    new_jti = str(uuid.uuid4())
    new_refresh_token = create_refresh_token(user, new_jti)
    new_expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db_new_refresh = RefreshToken(
        id=new_jti,
        user_id=user.user_id,
        expires_at=new_expires_at,
        device_info=request.headers.get("user-agent")
    )
    db.add(db_new_refresh)
    db.commit()

    new_access_token = create_access_token(user)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )

@router.post("/logout")
def logout(data: LogoutRequest, db: Session = Depends(get_db)):
    refresh_token = data.refresh_token
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_refresh = db.query(RefreshToken).filter(RefreshToken.id == jti).first()
    if db_refresh:
        db_refresh.revoked = True
        db.commit()

    return {"success": True, "message": "Сессия успешно завершена"}
