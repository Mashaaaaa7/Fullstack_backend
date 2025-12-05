from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.auth import get_current_user, verify_password, get_password_hash
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


# ===== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ =====
def log_action(
    db: Session,
    user_id: int,
    action: str,
    details: str,
    filename: str = None
):
    """Логирование действия в историю"""
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


# ===== ЭНДПОИНТЫ =====
@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Смена пароля"""
    # Получи юзера из БД
    user = db.query(User).filter(User.user_id == current_user.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Проверь текущий пароль
    try:
        if not verify_password(request.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Текущий пароль неверный"
            )
    except Exception as e:
        print(f"❌ Ошибка при проверке пароля: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка при проверке пароля"
        )

    # Проверь, что новый пароль отличается от старого
    try:
        if verify_password(request.new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Новый пароль совпадает со старым"
            )
    except HTTPException:
        raise
    except Exception:
        # Если не совпадает (ошибка при verify) — это хорошо
        pass

    # Обнови пароль
    try:
        user.hashed_password = get_password_hash(request.new_password)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка при обновлении пароля: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении пароля"
        )

    # Логируй действие
    log_action(
        db,
        user.user_id,
        "change_password",
        "Пароль успешно изменён"
    )

    return {
        "success": True,
        "message": "✅ Пароль успешно изменён"
    }


@router.post("/change-email", response_model=ChangeEmailResponse)
async def change_email(
    request: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Смена email"""
    user = db.query(User).filter(User.user_id == current_user.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Проверь пароль
    try:
        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пароль неверный"
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка при проверке пароля: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка при проверке пароля"
        )

    # Проверь, что новый email не занят
    existing_user = db.query(User).filter(User.email == request.new_email).first()
    if existing_user and existing_user.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован"
        )

    # Проверь, что email отличается от текущего
    if user.email == request.new_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый email совпадает с текущим"
        )

    # Обнови email
    try:
        old_email = user.email
        user.email = request.new_email
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка при обновлении email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении email"
        )

    # Логируй действие
    log_action(
        db,
        user.user_id,
        "change_email",
        f"Email изменён с {old_email} на {request.new_email}"
    )

    return {
        "success": True,
        "message": "✅ Email успешно изменён",
        "email": user.email
    }