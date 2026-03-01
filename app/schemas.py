from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class UserOut(BaseModel):
    user_id: int
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True

class Card(BaseModel):
    question: str
    answer: str

class CardList(BaseModel):
    cards: list[Card]

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"