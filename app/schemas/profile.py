from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional

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