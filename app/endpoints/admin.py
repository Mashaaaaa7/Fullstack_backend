from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import User, UserRole
from app.auth import get_current_user


class RoleUpdate(BaseModel):
    role: UserRole


router = APIRouter()


@router.get("/users")
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    users = db.query(User).all()

    return {
        "users": [
            {
                "id": u.user_id,
                "email": u.email,
                "role": u.role.value,
            }
            for u in users
        ]
    }


@router.put("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    payload: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    target_user = (
        db.query(User)
        .filter(User.user_id == user_id)   # ← ВАЖНО
        .first()
    )

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.role = payload.role
    db.commit()
    db.refresh(target_user)

    return {
        "success": True,
        "user_id": target_user.user_id,
        "role": target_user.role.value,
    }
