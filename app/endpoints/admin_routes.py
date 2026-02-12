from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
from app.auth import get_current_user

router = APIRouter(prefix="/admin")

@router.get("/users")
def list_users(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    return {"users": [{"id": u.id, "username": u.username, "role": u.role} for u in db.query(User).all()]}


@router.put("/users/{user_id}/role")
def change_user_role(user_id: int, role: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")

    user = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = role
    db.commit()
    return {"success": True, "id": u.id, "role": u.role}
