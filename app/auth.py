from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi.security import HTTPBearer
from datetime import timedelta, datetime
from fastapi import Depends, status
from app.database import SessionLocal
from app.models import User

router = APIRouter()

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
SECRET_KEY = "secret_KEY"
ALGORITHM = "HS256"
security = HTTPBearer()

def validate_password(password: str) -> bool:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен содержать не менее 8 символов"
        )
    return True

def get_password_hash(password: str) -> str:
    validate_password(password)
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials=Depends(security)):
    database = SessionLocal()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user = database.query(User).filter(User.user_id == int(user_id)).first()
        if user is None:
            raise credentials_exception

        return user

    except JWTError as e:
        print(f"JWT Error: {e}")
        raise credentials_exception

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