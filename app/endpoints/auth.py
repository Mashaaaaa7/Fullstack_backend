from fastapi import APIRouter, HTTPException, Depends, status, Request  # <-- добавили Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import User, UserRole


router = APIRouter(prefix="/api/auth")

SECRET_KEY = "secret_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24*60
REFRESH_TOKEN_EXPIRE_DAYS = 365
security = HTTPBearer()
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
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

# Создание access token
def create_access_token(user: User):
    expire = datetime.utcnow() + timedelta(hours=1)  # короткий срок
    payload = {"sub": user.email, "role": user.role.value, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# Создание refresh token
def create_refresh_token(user: User):
    expire = datetime.utcnow() + timedelta()
    payload = {"sub": user.email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if user_id is None or role is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id), role
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing token")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid token scheme")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
        if not email or not role:
            raise HTTPException(status_code=401, detail="Invalid token")
        # Возвращаем объект с email и role
        return {"email": email, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/register", response_model=TokenResponse)
def register(user: UserCreate):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == user.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        new_user = User(email=user.email, hashed_password=get_password_hash(user.password))
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        token = create_access_token(new_user)
        return {"access_token": token}
    finally:
        db.close()

@router.post("/login", response_model=TokenResponse)
def login(user: UserCreate):
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.email == user.email).first()
        if not db_user or not verify_password(user.password, db_user.hashed_password):
            raise HTTPException(status_code=400, detail="Invalid credentials")
        token = create_access_token(db_user)
        return {"access_token": token}
    finally:
        db.close()

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.value
    }

@router.post("/refresh-token", response_model=TokenResponse)
def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401)
        # получаем пользователя из БД
        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        db.close()
        if not user:
            raise HTTPException(status_code=404)
        new_access_token = create_access_token(user)
        return {"access_token": new_access_token}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")