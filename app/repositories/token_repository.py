from sqlalchemy.orm import Session

from app.models import RefreshToken


class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_refresh_token(self, user_id: int, expires_at):
        token = RefreshToken(
            user_id=user_id,
            expires_at=expires_at,
            revoked=False
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def get_refresh_token(self, token_id: str):
        return self.db.query(RefreshToken).filter(RefreshToken.id == token_id).first()

    def revoke_refresh_token(self, token_id: str):
        token = self.get_refresh_token(token_id)
        if token:
            token.revoked = True
            self.db.commit()
        return token