from sqlalchemy.orm import Session
from app.models import PDFFile, Flashcard, ProcessingStatus
from typing import List, Optional, Dict, Any

class PDFRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_pdf(self, file_name: str, file_key: str, size: int, mime_type: str, user_id: int) -> PDFFile:
        pdf = PDFFile(
            file_name=file_name,
            file_key=file_key,
            size=size,
            mime_type=mime_type,
            user_id=user_id,
            status=ProcessingStatus.UPLOADED
        )
        self.db.add(pdf)
        self.db.commit()
        self.db.refresh(pdf)
        return pdf

    def get_pdf_by_id(self, file_id: int) -> Optional[PDFFile]:
        return self.db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.is_deleted == False
        ).first()

    def get_pdf_by_key(self, file_key: str) -> Optional[PDFFile]:
        return self.db.query(PDFFile).filter(PDFFile.file_key == file_key).first()

    def update_status(self, file_id: int, status: ProcessingStatus):
        self.db.query(PDFFile).filter(PDFFile.id == file_id).update({"status": status})
        self.db.commit()

    def soft_delete_pdf(self, file_id: int):
        self.db.query(PDFFile).filter(PDFFile.id == file_id).update({"is_deleted": True})
        self.db.commit()

    def get_user_pdfs(self, user_id: int, admin: bool = False) -> List[PDFFile]:
        query = self.db.query(PDFFile).filter(PDFFile.is_deleted == False)
        if not admin:
            query = query.filter(PDFFile.user_id == user_id)
        return query.all()

    def save_flashcards(self, pdf_file_id: int, user_id: int, flashcards_data: List[Dict[str, Any]]) -> List[Flashcard]:
        saved_cards = []
        for card_data in flashcards_data:
            flashcard = Flashcard(
                pdf_file_id=pdf_file_id,
                user_id=user_id,
                question=card_data.get("question"),
                answer=card_data.get("answer"),
                context=card_data.get("context"),
                source=card_data.get("source")
            )
            self.db.add(flashcard)
            saved_cards.append(flashcard)
        self.db.commit()
        for card in saved_cards:
            self.db.refresh(card)
        return saved_cards

    def get_cards_for_pdf(
        self,
        pdf_file_id: int,
        user_id: Optional[int] = None,
        admin: bool = False,
        skip: int = 0,
        limit: int = 6
    ) -> List[Flashcard]:
        query = self.db.query(Flashcard).filter(Flashcard.pdf_file_id == pdf_file_id)
        if not admin and user_id is not None:
            query = query.filter(Flashcard.user_id == user_id)
        return query.order_by(Flashcard.id).offset(skip).limit(limit).all()

    def count_cards_for_pdf(
        self,
        pdf_file_id: int,
        user_id: Optional[int] = None,
        admin: bool = False
    ) -> int:
        query = self.db.query(Flashcard).filter(Flashcard.pdf_file_id == pdf_file_id)
        if not admin and user_id is not None:
            query = query.filter(Flashcard.user_id == user_id)
        return query.count()