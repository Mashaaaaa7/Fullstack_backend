import os
import tempfile
from typing import Dict, Any, Optional

from fastapi import HTTPException, UploadFile
from minio.error import S3Error
from sqlalchemy.orm import Session

from app.repositories.pdf_repository import PDFRepository
from app.repositories.history_repository import HistoryRepository
from app.repositories.actionlog_repository import ActionLogRepository
from app.models import User, ProcessingStatus, ActionType, PDFFile
from app.services.qa_generator_service import QAGeneratorService
from app.minio_client import (
    upload_file_to_minio,
    delete_file_from_minio,
    generate_presigned_url,
    MINIO_BUCKET_PDF,
)
from app.database import SessionLocal


class PDFService:
    def __init__(self, db: Session, qa_service: QAGeneratorService):
        self.db = db
        self.pdf_repo = PDFRepository(db)
        self.history_repo = HistoryRepository(db)
        self.action_log_repo = ActionLogRepository(db)
        self.qa_service = qa_service

    def _get_owned_pdf(self, file_id: int, user: User) -> PDFFile:
        pdf_file = self.pdf_repo.get_pdf_by_id(file_id)
        if not pdf_file or pdf_file.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="PDF not found")
        return pdf_file

    async def upload_pdf(self, file: UploadFile, user: User) -> Dict[str, Any]:
        contents = await file.read()
        file_size = len(contents)

        # 1. Ограничение размера: до 10 МБ
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max 10 MB")

        # 2. Проверка имени файла и расширения
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # 3. Проверка content_type от клиента
        if file.content_type not in ("application/pdf", "application/x-pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # 4. Проверка сигнатуры файла (magic number)
        if not contents.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Invalid PDF file")

        from app.minio_client import generate_file_key

        file_key = generate_file_key(file.filename)

        await upload_file_to_minio(
            file_data=contents,
            bucket=MINIO_BUCKET_PDF,
            object_name=file_key,
            content_type=file.content_type or "application/pdf",
        )

        db_file = self.pdf_repo.create_pdf(
            file_name=file.filename,
            file_key=file_key,
            size=file_size,
            mime_type=file.content_type or "application/pdf",
            user_id=user.user_id,
        )

        return {
            "success": True,
            "file_id": db_file.id,
            "file_name": file.filename,
        }

    def start_processing(self, file_id: int, user: User) -> PDFFile:
        return self._get_owned_pdf(file_id, user)

    def process_pdf_sync(
        self,
        file_id: int,
        file_key: str,
        filename: str,
        user_id: int,
        max_cards: int,
    ):
        db = SessionLocal()
        tmp_path = None
        try:
            pdf_repo = PDFRepository(db)
            history_repo = HistoryRepository(db)
            action_log_repo = ActionLogRepository(db)

            from app.minio_client import client

            try:
                info = client.stat_object(MINIO_BUCKET_PDF, file_key)
                print(f"✅ Объект найден в MinIO: {file_key}, размер {info.size} байт")
            except S3Error as e:
                print(f"❌ Объект {file_key} не найден в MinIO: {e}")
                raise Exception(
                    f"Объект {file_key} не существует в бакете {MINIO_BUCKET_PDF}"
                )

            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)

            client.fget_object(MINIO_BUCKET_PDF, file_key, tmp_path)

            downloaded_size = os.path.getsize(tmp_path)
            print(f"📥 Скачано {downloaded_size} байт в {tmp_path}")
            if downloaded_size == 0:
                raise Exception(
                    f"Скачанный файл пуст, ожидалось {info.size} байт"
                )

            flashcards = self.qa_service.process_pdf(tmp_path, max_cards)

            pdf_repo.save_flashcards(file_id, user_id, flashcards)
            pdf_repo.update_status(file_id, ProcessingStatus.PROCESSED)

            history_repo.add_action(
                user_id=user_id,
                action="process",
                details=f"Обработано {len(flashcards)} карточек",
                filename=filename,
            )

            action_log_repo.create(
                user_id=user_id,
                file_id=file_id,
                action=ActionType.GENERATE_CARDS,
                details={"count": len(flashcards)},
            )

            db.commit()
        except Exception as e:
            pdf_repo.update_status(file_id, ProcessingStatus.FAILED)
            db.commit()
            import traceback

            traceback.print_exc()
            print(f"Ошибка обработки PDF {file_id}: {e}")
        finally:
            db.close()
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    print(f"🗑 Временный файл {tmp_path} удалён")
                except Exception as e:
                    print(f"Не удалось удалить временный файл {tmp_path}: {e}")

    def get_download_url(self, file_id: int, user: User) -> Dict[str, Any]:
        pdf_file = self._get_owned_pdf(file_id, user)
        try:
            url = generate_presigned_url(
                MINIO_BUCKET_PDF, pdf_file.file_key, expires=3600
            )
        except Exception as e:
            print(f"Ошибка генерации pre-signed URL для файла {file_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Не удалось сгенерировать ссылку для скачивания",
            )

        self.action_log_repo.create(
            user_id=user.user_id,
            file_id=file_id,
            action=ActionType.DOWNLOAD,
            details={"url_expires_in": 3600},
        )
        return {"download_url": url}

    def list_pdfs_filtered(
        self,
        user: User,
        page: int = 1,
        limit: int = 10,
        status: Optional[ProcessingStatus] = None,
        search: Optional[str] = None,
        sort: str = "created_at_desc",
    ) -> Dict[str, Any]:
        query = self.db.query(PDFFile).filter(
            ~PDFFile.is_deleted,
            PDFFile.user_id == user.user_id,
        )
        if search:
            query = query.filter(PDFFile.file_name.ilike(f"%{search}%"))
        if status:
            query = query.filter(PDFFile.status == status)
        if sort == "created_at_desc":
            query = query.order_by(PDFFile.created_at.desc())
        elif sort == "created_at_asc":
            query = query.order_by(PDFFile.created_at.asc())
        elif sort == "name_asc":
            query = query.order_by(PDFFile.file_name.asc())
        elif sort == "name_desc":
            query = query.order_by(PDFFile.file_name.desc())

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()

        return {
            "success": True,
            "items": [
                {
                    "id": pdf.id,
                    "file_name": pdf.file_name,
                    "size": pdf.size,
                    "status": pdf.status.value,
                    "created_at": pdf.created_at.isoformat()
                    if pdf.created_at
                    else None,
                    "owner_id": pdf.user_id,
                }
                for pdf in items
            ],
            "total": total,
            "page": page,
            "limit": limit,
        }

    def get_cards(
        self, file_id: int, user: User, skip: int = 0, limit: int = 10
    ) -> Dict[str, Any]:
        pdf_file = self._get_owned_pdf(file_id, user)
        cards = self.pdf_repo.get_cards_for_pdf(
            file_id, user.user_id, skip=skip, limit=limit
        )
        total = self.pdf_repo.count_cards_for_pdf(file_id, user.user_id)
        return {
            "success": True,
            "file_name": pdf_file.file_name,
            "cards": [
                {
                    "id": c.id,
                    "question": c.question,
                    "answer": c.answer,
                    "context": c.context,
                    "source": c.source,
                    "is_hidden": c.is_hidden,
                    "is_deleted": c.is_deleted,
                    "created_at": c.created_at.isoformat()
                    if c.created_at
                    else None,
                }
                for c in cards
            ],
            "total": total,
        }

    def delete_pdf(self, file_id: int, user: User) -> Dict[str, Any]:
        pdf_file = self._get_owned_pdf(file_id, user)
        delete_file_from_minio(MINIO_BUCKET_PDF, pdf_file.file_key)
        self.pdf_repo.soft_delete_pdf(file_id)
        self.history_repo.add_action(
            user_id=user.user_id,
            action="delete",
            details="Файл удалён",
            filename=pdf_file.file_name,
        )
        self.action_log_repo.create(
            user_id=user.user_id,
            file_id=file_id,
            action=ActionType.DELETE,
            details={"filename": pdf_file.file_name},
        )
        return {"success": True, "message": f"{pdf_file.file_name} deleted"}

    def get_history(self, user: User, limit: int = 50) -> Dict[str, Any]:
        actions = self.history_repo.get_user_history(user.user_id)[:limit]
        return {
            "success": True,
            "history": [
                {
                    "id": a.id,
                    "action": a.action,
                    "filename": a.filename,
                    "details": a.details,
                    "created_at": a.created_at.isoformat()
                    if a.created_at
                    else None,
                }
                for a in actions
            ],
        }