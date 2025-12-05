from app.models import User
from app.database import SessionLocal

db = SessionLocal()
try:
    # Удалить ВСЕХ
    deleted_count = db.query(User).delete()

    # ИЛИ удалить по email (раскомментируй нужное)
    # deleted_count = db.query(User).filter(User.email == 'user@example.com').delete()

    db.commit()
    print(f"✅ Удалено пользователей: {deleted_count}")
finally:
    db.close()