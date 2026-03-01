from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from typing import Optional
from app.utils.security import verify_password, get_password_hash
from app.endpoints.auth import get_current_user
from app.database import get_db
from app.models import User
from app import crud

router = APIRouter()

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Пароль должен быть минимум 8 символов')
        if len(v) > 100:
            raise ValueError('Пароль слишком длинный')
        return v

    @field_validator('confirm_password')
    @classmethod
    def validate_confirm(cls, v: str, info) -> str:
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Пароли не совпадают')
        return v

class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    password: str

class ChangeEmailResponse(BaseModel):
    success: bool
    message: str
    email: Optional[str] = None

# --- Логирование ---
def log_action(
    db: Session,
    user_id: int,
    action: str,
    details: str,
    filename: str = None
):
    try:
        crud.add_action(
            db=db,
            action=action,
            details=details,
            filename=filename,
            user_id=user_id
        )
    except Exception as e:
        print(f"⚠️ Ошибка логирования: {e}")

# --- Эндпоинты ---
@router.get("/me")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.value
    }

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка текущего пароля
    if not verify_password(request.current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Текущий пароль неверный")

    # Проверка, что новый пароль отличается от старого
    if verify_password(request.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Новый пароль совпадает со старым")

    # Обновление пароля
    user.hashed_password = get_password_hash(request.new_password)
    db.commit()

    log_action(db, user.user_id, "change_password", "Пароль успешно изменён")
    return {"success": True, "message": "✅ Пароль успешно изменён"}

@router.post("/change-email", response_model=ChangeEmailResponse)
async def change_email(
    request: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка пароля
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Пароль неверный")

    # Проверка, что email не занят другим пользователем
    existing_user = db.query(User).filter(User.email == request.new_email).first()
    if existing_user and existing_user.user_id != user.user_id:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    # Проверка, что новый email отличается от текущего
    if user.email == request.new_email:
        raise HTTPException(status_code=400, detail="Новый email совпадает с текущим")

    # Обновление email
    old_email = user.email
    user.email = request.new_email
    db.commit()

    log_action(db, user.user_id, "change_email", f"Email изменён с {old_email} на {request.new_email}")
    return {
        "success": True,
        "message": "✅ Email успешно изменён",
        "email": user.email
    }