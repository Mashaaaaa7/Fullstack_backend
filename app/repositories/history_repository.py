from sqlalchemy.orm import Session
from app.models import ActionHistory

class HistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_action(self, user_id, action, details, filename):
        record = ActionHistory(
            user_id=user_id,
            action=action,
            details=details,
            filename=filename
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_user_history(self, user_id: int, limit: int = 50) -> list[type[ActionHistory]]:
        return self.db.query(ActionHistory).filter(
            ActionHistory.user_id == user_id
        ).order_by(ActionHistory.created_at.desc()).limit(limit).all()

    def get_all_history(self) -> list[type[ActionHistory]]:
        return self.db.query(ActionHistory).order_by(ActionHistory.created_at.desc()).all()