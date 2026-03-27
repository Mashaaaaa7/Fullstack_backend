from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.repositories.user_repository import UserRepository
from app.models import User, UserRole
from typing import List, Dict, Any

class AdminService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def list_users(self, current_user: User) -> List[Dict[str, Any]]:
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="Access denied")
        users = self.user_repo.db.query(User).all()
        return [{"user_id": u.user_id, "email": u.email, "role": u.role.value} for u in users]

    def change_user_role(self, current_user: User, target_user_id: int, new_role: UserRole) -> Dict[str, Any]:
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="Access denied")
        if current_user.user_id == target_user_id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        user = self.user_repo.get_by_id(target_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        self.user_repo.update_role(target_user_id, new_role.value)
        return {"success": True, "user_id": target_user_id, "role": new_role.value}