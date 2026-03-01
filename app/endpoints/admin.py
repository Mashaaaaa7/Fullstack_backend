from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
from app.endpoints.auth import get_current_user
from pydantic import BaseModel

router = APIRouter()

class RoleUpdate(BaseModel):
    role: UserRole

@router.get("/users")
def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"users": [{"user_id": u.user_id, "email": u.email, "role": u.role.value} for u in db.query(User).all()]}

@router.put("/users/{user_id}/role")
def change_user_role(user_id: int, payload: RoleUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")
    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = payload.role
    db.commit()
    db.refresh(target)
    return {"success": True, "user_id": target.user_id, "role": target.role.value}