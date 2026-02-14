from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import User, UserRole

router = APIRouter()

SECRET_KEY = "secret_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1
security = HTTPBearer()
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    user_id: int
    email: str
    role: str


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

def create_access_token(user: User):
    to_encode = {
        "sub": str(user.user_id),
        "role": user.role.value  # user или admin
    }
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None or role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return int(user_id), role
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(credentials=Depends(security)):
    db = SessionLocal()
    try:
        token = credentials.credentials
        user_id, role = decode_token(token)
        user = db.query(User).filter(User.user_id == user_id).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    finally:
        db.close()

@router.post("/register", response_model=TokenResponse)
def register(user: UserCreate):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == user.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed, role=UserRole.user)
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
def refresh_token(current_user: User = Depends(get_current_user)):
    access_token = create_access_token(current_user)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }