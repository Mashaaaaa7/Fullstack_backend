from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.admin import RoleUpdate
from app.services.admin_service import AdminService
from app.core.dependencies import get_db, get_current_user
from app.models import User

router = APIRouter()

@router.get("/users")
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = AdminService(db)
    users = service.list_users(current_user)
    return {"users": users}

@router.put("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    payload: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = AdminService(db)
    return service.change_user_role(current_user, user_id, payload.role)