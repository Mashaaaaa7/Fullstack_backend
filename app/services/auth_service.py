from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token
)
from app.repositories.user_repository import UserRepository
from app.repositories.token_repository import TokenRepository

class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)
        self.token_repo = TokenRepository(db)

    def register(self, email: str, password: str):
        if self.user_repo.get_by_email(email):
            raise HTTPException(status_code=400, detail="Email already registered")
        hashed = get_password_hash(password)
        user = self.user_repo.create_user(email, hashed, role="user")
        return self._create_tokens(user)

    def login(self, email: str, password: str):
        user = self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return self._create_tokens(user)

    def refresh(self, refresh_token: str):
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
        jti = payload.get("jti")
        user_id = int(payload.get("sub"))
        db_token = self.token_repo.get_refresh_token(jti)
        if not db_token or db_token.revoked or db_token.expires_at < datetime.utcnow() or db_token.user_id != user_id:
            raise HTTPException(status_code=401, detail="Refresh token revoked or expired")
        # ротация
        self.token_repo.revoke_refresh_token(jti)
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return self._create_tokens(user)

    def logout(self, refresh_token: str):
        payload = decode_token(refresh_token)
        if payload:
            jti = payload.get("jti")
            self.token_repo.revoke_refresh_token(jti)

    def _create_tokens(self, user):
        access = create_access_token(user.user_id, user.role.value)
        expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        token = self.token_repo.create_refresh_token(user.user_id, expires)
        refresh = create_refresh_token(user.user_id, token.id)
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}