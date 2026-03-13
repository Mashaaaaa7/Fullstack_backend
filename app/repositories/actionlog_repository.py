from sqlalchemy.orm import Session
from app.models import ActionLog, ActionType
from typing import Optional, List, Dict


class ActionLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, file_id: int, action: ActionType, details: Optional[Dict] = None) -> ActionLog:
        log = ActionLog(user_id=user_id, file_id=file_id, action=action, details=details)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_by_file(self, file_id: int, limit: int = 50) -> List[ActionLog]:
        return self.db.query(ActionLog).filter(ActionLog.file_id == file_id).order_by(ActionLog.timestamp.desc()).limit(
            limit).all()

    def get_by_user(self, user_id: int, limit: int = 50) -> List[ActionLog]:
        return self.db.query(ActionLog).filter(ActionLog.user_id == user_id).order_by(ActionLog.timestamp.desc()).limit(
            limit).all()