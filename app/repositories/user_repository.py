from sqlalchemy.orm import Session
from app.models import User

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.user_id == user_id).first()

    def create_user(self, email: str, hashed_password: str, role: str) -> User:
        user = User(email=email, hashed_password=hashed_password, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user_id: int, new_hashed_password: str) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.hashed_password = new_hashed_password
            self.db.commit()
            self.db.refresh(user)
        return user

    def update_email(self, user_id: int, new_email: str) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.email = new_email
            self.db.commit()
            self.db.refresh(user)
        return user

    def update_role(self, user_id: int, new_role: str) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.role = new_role
            self.db.commit()
            self.db.refresh(user)
        return user