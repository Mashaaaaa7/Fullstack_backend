from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.core.dependencies import get_db, require_role
from app.models import User, UserRole
from app.schemas.admin import PaginatedUsersResponse, UserOut, RoleUpdate
from app.services.admin_service import AdminService

router = APIRouter(tags=["admin"])

@router.get("/users", response_model=PaginatedUsersResponse)
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[str] = Query(None, regex="^(user|admin)$"),
    sort: str = Query("email_asc", regex="^(email_asc|email_desc|created_at_asc|created_at_desc|role_asc|role_desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin))
):
    # Базовый запрос
    query = db.query(User)

    # Поиск по email
    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))

    # Фильтр по роли
    if role:
        query = query.filter(User.role == role)

    # Сортировка
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

    # Пагинация
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