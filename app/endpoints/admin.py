from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.dependencies import get_db, require_role
from app.models import User, UserRole
from app.schemas.admin import RoleUpdate
from app.services.admin_service import AdminService

router = APIRouter()

@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    query = db.query(User)

    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))

    if role:
        query = query.filter(User.role == role)

    if sort == "email_asc":
        query = query.order_by(User.email.asc())
    elif sort == "email_desc":
        query = query.order_by(User.email.desc())
    elif sort == "created_at_asc":
        query = query.order_by(User.created_at.asc())
    elif sort == "created_at_desc":
        query = query.order_by(User.created_at.desc())
    elif sort == "role_asc":
        query = query.order_by(User.role.asc())
    elif sort == "role_desc":
        query = query.order_by(User.role.desc())

    total = query.count()
    users = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "success": True,
        "total": total,
        "page": page,
        "limit": limit,
        "items": users
    }

@router.put("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    payload: RoleUpdate,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    service = AdminService(db)
    return service.change_user_role(current_user, user_id, payload.role)