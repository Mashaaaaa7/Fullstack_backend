import os
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
from typing import Dict, Any
from app.repositories.pdf_repository import PDFRepository
from app.repositories.history_repository import HistoryRepository
from app.models import User, UserRole
from app.services.qa_generator_service import QAGeneratorService

class PDFService:
    def __init__(self, db: Session):
        self.pdf_repo = PDFRepository(db)
        self.history_repo = HistoryRepository(db)
        self.qa_service = QAGeneratorService()

    async def upload_pdf(self, file: UploadFile, user: User) -> Dict[str, Any]:
        folder = f"uploads/{user.user_id}/"
        os.makedirs(folder, exist_ok=True)
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(folder, unique_filename)
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        db_file = self.pdf_repo.create_pdf(file.filename, file_path, user.user_id)
        self.history_repo.add_action(
            user_id=user.user_id,
            action="upload",
            details="Файл загружен",
            filename=file.filename
        )
        return {"success": True, "file_id": db_file.id, "file_name": file.filename}

    def start_processing(self, file_id: int, user: User, max_cards: int):
        pdf_file = self.pdf_repo.get_pdf_by_id(file_id)
        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")
        if user.role != UserRole.admin and pdf_file.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="PDF not found")
        return pdf_file

    def process_pdf_sync(self, file_id: int, file_path: str, filename: str, user_id: int, max_cards: int):
        """Синхронная функция для фоновой обработки"""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            print(f"🔄 Обрабатываю {filename}...")
            flashcards = self.qa_service.process_pdf(file_path, max_cards)
            pdf_repo = PDFRepository(db)
            pdf_repo.save_flashcards(file_id, user_id, flashcards)
            history_repo = HistoryRepository(db)
            history_repo.add_action(
                user_id=user_id,
                action="process",
                details=f"Обработано {len(flashcards)} карточек",
                filename=filename
            )
            db.commit()
            print(f"✅ Готово! {len(flashcards)} карточек")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            db.close()

    def list_pdfs(self, user: User) -> Dict[str, Any]:
        is_admin = (user.role == UserRole.admin)
        pdfs = self.pdf_repo.get_user_pdfs(user.user_id, admin=is_admin)
        result = []
        for p in pdfs:
            size = os.path.getsize(p.file_path) if os.path.exists(p.file_path) else 0
            result.append({"id": p.id, "name": p.file_name, "file_size": size})
        return {"success": True, "pdfs": result, "total": len(result)}

    def get_cards(self, file_id: int, user: User, skip: int = 0, limit: int = 10) -> Dict[str, Any]:
        pdf_file = self.pdf_repo.get_pdf_by_id(file_id)
        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")
        if user.role != UserRole.admin and pdf_file.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="PDF not found")
        is_admin = (user.role == UserRole.admin)
        cards = self.pdf_repo.get_cards_for_pdf(file_id, user.user_id, admin=is_admin, skip=skip, limit=limit)
        total = self.pdf_repo.count_cards_for_pdf(file_id, user.user_id, admin=is_admin)
        return {
            "success": True,
            "file_name": pdf_file.file_name,
            "cards": cards,
            "total": total
        }

    def delete_pdf(self, file_id: int, user: User) -> Dict[str, Any]:
        pdf_file = self.pdf_repo.get_pdf_by_id(file_id)
        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")
        if user.role != UserRole.admin and pdf_file.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="PDF not found")
        self.pdf_repo.soft_delete_pdf(file_id)
        self.history_repo.add_action(
            user_id=user.user_id,
            action="delete",
            details="Файл удалён",
            filename=pdf_file.file_name
        )
        return {"success": True, "message": f"{pdf_file.file_name} deleted"}

    def get_history(self, user: User, limit: int = 50) -> Dict[str, Any]:
        if user.role == UserRole.admin:
            actions = self.history_repo.get_all_history()[:limit]
        else:
            actions = self.history_repo.get_user_history(user.user_id)[:limit]
        return {
            "success": True,
            "history": [
                {
                    "id": a.id,
                    "action": a.action,
                    "filename": a.filename,
                    "details": a.details,
                    "created_at": a.created_at.isoformat() if a.created_at else None
                } for a in actions
            ]
        }