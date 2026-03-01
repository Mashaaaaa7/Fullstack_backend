from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.auth import UserCreate, TokenResponse, RefreshRequest, LogoutRequest
from app.services.auth_service import AuthService
from app.core.dependencies import get_db

router = APIRouter()

@router.post("/register", response_model=TokenResponse)
def register(data: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.register(data.email, data.password)

@router.post("/login", response_model=TokenResponse)
def login(data: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.login(data.email, data.password)

@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.refresh(data.refresh_token)

@router.post("/logout")
def logout(data: LogoutRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    service.logout(data.refresh_token)
    return {"success": True, "message": "Logged out"}