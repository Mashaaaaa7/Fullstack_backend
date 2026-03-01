from sqlalchemy.orm import Session
from app.models import PDFFile, Flashcard
from typing import List, Optional

class PDFRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_pdf(self, file_name: str, file_path: str, user_id: int) -> PDFFile:
        pdf = PDFFile(file_name=file_name, file_path=file_path, user_id=user_id)
        self.db.add(pdf)
        self.db.commit()
        self.db.refresh(pdf)
        return pdf

    def get_pdf_by_id(self, pdf_id: int) -> Optional[PDFFile]:
        return self.db.query(PDFFile).filter(
            PDFFile.id == pdf_id,
            PDFFile.is_deleted == False
        ).first()

    def get_user_pdfs(self, user_id: int, admin: bool = False) -> List[PDFFile]:
        query = self.db.query(PDFFile).filter(PDFFile.is_deleted == False)
        if not admin:
            query = query.filter(PDFFile.user_id == user_id)
        return query.all()

    def soft_delete_pdf(self, pdf_id: int) -> Optional[PDFFile]:
        pdf = self.get_pdf_by_id(pdf_id)
        if pdf:
            pdf.is_deleted = True
            self.db.commit()
            self.db.refresh(pdf)
        return pdf

    def save_flashcards(self, pdf_file_id: int, user_id: int, flashcards_data: List[dict]) -> List[Flashcard]:
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

    def get_cards_for_pdf(self, pdf_file_id: int, user_id: Optional[int] = None, admin: bool = False) -> List[Flashcard]:
        query = self.db.query(Flashcard).filter(Flashcard.pdf_file_id == pdf_file_id)
        if not admin and user_id is not None:
            query = query.filter(Flashcard.user_id == user_id)
        return query.limit(10).all()