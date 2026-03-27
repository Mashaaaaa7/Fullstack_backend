from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.repositories.user_repository import UserRepository
from app.repositories.history_repository import HistoryRepository
from app.core.security import verify_password, get_password_hash

class UserService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)
        self.history_repo = HistoryRepository(db)

    def get_profile(self, user_id: int):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "user_id": user.user_id,
            "email": user.email,
            "role": user.role.value
        }

    def change_password(self, user_id: int, current_password: str, new_password: str):
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        if verify_password(new_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="New password must be different")
        new_hashed = get_password_hash(new_password)
        self.user_repo.update_password(user_id, new_hashed)
        self.history_repo.add_action(
            user_id=user_id,
            action="change_password",
            details="Password changed"
        )

    def change_email(self, user_id: int, password: str, new_email: str) -> str:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Password is incorrect")
        existing = self.user_repo.get_by_email(new_email)
        if existing and existing.user_id != user_id:
            raise HTTPException(status_code=400, detail="Email already registered")
        if user.email == new_email:
            raise HTTPException(status_code=400, detail="New email is the same as current")
        old_email = user.email
        self.user_repo.update_email(user_id, new_email)
        self.history_repo.add_action(
            user_id=user_id,
            action="change_email",
            details=f"Email changed from {old_email} to {new_email}"
        )
        return new_email