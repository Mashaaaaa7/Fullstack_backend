from sqlalchemy.orm import Session
from app.models import RefreshToken
from datetime import datetime
import uuid

class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_refresh_token(self, user_id: int, expires_at: datetime) -> RefreshToken:
        jti = str(uuid.uuid4())
        token = RefreshToken(
            id=jti,
            user_id=user_id,
            expires_at=expires_at,
            revoked=False  # по умолчанию False
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def get_refresh_token(self, jti: str) -> RefreshToken | None:
        return self.db.query(RefreshToken).filter(RefreshToken.id == jti).first()

    def revoke_refresh_token(self, jti: str) -> None:
        token = self.get_refresh_token(jti)
        if token:
            token.revoked = True
            self.db.commit()