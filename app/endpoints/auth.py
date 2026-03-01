from fastapi import APIRouter, Depends, Response, Request, HTTPException
from sqlalchemy.orm import Session
from app.schemas.auth import UserCreate, TokenResponse
from app.services.auth_service import AuthService
from app.core.dependencies import get_db
from app.core.config import settings

router = APIRouter()

@router.post("/register", response_model=TokenResponse)
def register(data: UserCreate, response: Response, db: Session = Depends(get_db)):
    service = AuthService(db)
    tokens = service.register(data.email, data.password)

    # Устанавливаем refresh token в httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,  # для HTTPS (в разработке можно False)
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    # Возвращаем только access token в теле
    return TokenResponse(access_token=tokens["access_token"], token_type="bearer")


@router.post("/login", response_model=TokenResponse)
def login(data: UserCreate, response: Response, db: Session = Depends(get_db)):
    service = AuthService(db)
    tokens = service.login(data.email, data.password)

    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return TokenResponse(access_token=tokens["access_token"], token_type="bearer")


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    # Читаем refresh token из cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    service = AuthService(db)
    tokens = service.refresh(refresh_token)

    # Устанавливаем новый refresh token в cookie (ротация)
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return TokenResponse(access_token=tokens["access_token"], token_type="bearer")


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        service = AuthService(db)
        service.logout(refresh_token)

    # Удаляем cookie на клиенте
    response.delete_cookie("refresh_token")

    return {"success": True, "message": "Logged out"}