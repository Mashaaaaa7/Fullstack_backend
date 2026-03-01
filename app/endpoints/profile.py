from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.profile import ChangePasswordRequest, ChangeEmailRequest, ChangeEmailResponse
from app.services.user_service import UserService
from app.core.dependencies import get_db, get_current_user
from app.models import User

router = APIRouter()

@router.get("/me")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.value
    }

@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = UserService(db)
    service.change_password(current_user.user_id, request.current_password, request.new_password)
    return {"success": True, "message": "✅ Пароль успешно изменён"}

@router.post("/change-email", response_model=ChangeEmailResponse)
def change_email(
    request: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = UserService(db)
    new_email = service.change_email(current_user.user_id, request.password, request.new_email)
    return {
        "success": True,
        "message": "✅ Email успешно изменён",
        "email": new_email
    }