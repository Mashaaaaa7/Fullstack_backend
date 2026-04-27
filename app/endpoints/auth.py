from fastapi import APIRouter, Depends, Response, Request, HTTPException
from sqlalchemy.orm import Session
from app.schemas.auth import UserCreate, TokenResponse
from app.services.auth_service import AuthService
from app.core.dependencies import get_db
from app.core.config import settings

router = APIRouter()


def set_refresh_cookie(response: Response, refresh_token: str):
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@router.post("/register", response_model=TokenResponse)
def register(data: UserCreate, response: Response, db: Session = Depends(get_db)):
    service = AuthService(db)
    tokens = service.register(data.email, data.password)
    set_refresh_cookie(response, tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post("/login", response_model=TokenResponse)
def login(data: UserCreate, response: Response, db: Session = Depends(get_db)):
    service = AuthService(db)
    tokens = service.login(data.email, data.password)
    set_refresh_cookie(response, tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    service = AuthService(db)
    tokens = service.refresh(refresh_token)
    set_refresh_cookie(response, tokens["refresh_token"])
    return TokenResponse(**tokens)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        service = AuthService(db)
        service.logout(refresh_token)

    response.delete_cookie(
        key="refresh_token",
        path="/",
        samesite="lax",
        secure=False,
    )
    return {"success": True, "message": "Logged out"}