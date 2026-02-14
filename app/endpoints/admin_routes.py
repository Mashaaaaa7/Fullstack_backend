router = APIRouter(prefix="/admin")

@router.get("/users")
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    users = db.query(User).all()

    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role
            }
            for u in users
        ]
    }

@router.put("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    role = data.get("role")

    if role not in (UserRole.user, UserRole.admin):
        raise HTTPException(status_code=400, detail="Invalid role")

    target_user = db.query(User).filter(User.id == user_id).first()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.role = role
    db.commit()
    db.refresh(target_user)

    return {
        "success": True,
        "user_id": target_user.id,
        "role": target_user.role
    }
