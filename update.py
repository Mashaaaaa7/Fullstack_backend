from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, UserRole

# === Настройки базы ===
DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ID пользователя, которого хотим сделать админом
TARGET_USER_ID = 1  

def make_admin(user_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            print(f"❌ Пользователь с ID {user_id} не найден")
            return

        user.role = UserRole.admin
        db.commit()
        print(f"✅ Пользователь {user.email} теперь админ")
    finally:
        db.close()

if __name__ == "__main__":
    make_admin(TARGET_USER_ID)
