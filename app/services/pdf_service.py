import os
import tempfile
import magic
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
from typing import Dict, Any, Optional, List
from sqlalchemy import or_
from minio.error import S3Error

from app.repositories.pdf_repository import PDFRepository
from app.repositories.history_repository import HistoryRepository
from app.repositories.actionlog_repository import ActionLogRepository
from app.models import User, UserRole, ProcessingStatus, ActionType, ActionLog, PDFFile
from app.services.qa_generator_service import QAGeneratorService
from app.minio_client import (
    upload_file_to_minio, delete_file_from_minio,
    generate_presigned_url, MINIO_BUCKET_PDF
)
from app.database import SessionLocal

class PDFService:
    def __init__(self, db: Session):
        self.db = db
        self.pdf_repo = PDFRepository(db)
        self.history_repo = HistoryRepository(db)
        self.action_log_repo = ActionLogRepository(db)
        self.qa_service = QAGeneratorService()

    async def upload_pdf(self, file: UploadFile, user: User) -> Dict[str, Any]:
        # Проверка размера
        contents = await file.read()
        file_size = len(contents)
        if file_size > 10 * 1024 * 1024:  # 10 MB
            raise HTTPException(status_code=400, detail="File too large. Max 10 MB")

        # Проверка MIME
        mime = magic.from_buffer(contents, mime=True)
        if mime != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # Загрузка в MinIO
        file_key = await upload_file_to_minio(file, MINIO_BUCKET_PDF)

        # Создание записи в БД
        db_file = self.pdf_repo.create_pdf(
            file_name=file.filename,
            file_key=file_key,
            size=file_size,
            mime_type=mime,
            user_id=user.user_id
        )

        # Логирование в старую историю
        self.history_repo.add_action(
            user_id=user.user_id,
            action="upload",
            details="Файл загружен в MinIO",
            filename=file.filename
        )

        # Логирование в ActionLog
        self.action_log_repo.create(
            user_id=user.user_id,
            file_id=db_file.id,
            action=ActionType.UPLOAD,
            details={"filename": file.filename, "size": file_size}
        )

        return {"success": True, "file_id": db_file.id, "file_name": file.filename}

    def start_processing(self, file_id: int, user: User, max_cards: int):
        pdf_file = self.pdf_repo.get_pdf_by_id(file_id)
        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")
        if user.role != UserRole.admin and pdf_file.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="PDF not found")
        return pdf_file

    def process_pdf_sync(self, file_id: int, file_key: str, filename: str, user_id: int, max_cards: int):
        db = SessionLocal()
        tmp_path = None
        try:
            pdf_repo = PDFRepository(db)
            history_repo = HistoryRepository(db)
            action_log_repo = ActionLogRepository(db)

            from app.minio_client import client, MINIO_BUCKET_PDF

            # Проверяем, существует ли объект в MinIO и не пустой ли он
            try:
                info = client.stat_object(MINIO_BUCKET_PDF, file_key)
                print(f"✅ Объект найден в MinIO: {file_key}, размер {info.size} байт")
            except S3Error as e:
                print(f"❌ Объект {file_key} не найден в MinIO: {e}")
                raise Exception(f"Объект {file_key} не существует в бакете {MINIO_BUCKET_PDF}")

            # Создаём временный файл (можно указать конкретную папку, если нужно)
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)

            # Скачиваем из MinIO
            client.fget_object(MINIO_BUCKET_PDF, file_key, tmp_path)

            # Проверяем, что файл не пустой
            downloaded_size = os.path.getsize(tmp_path)
            print(f"📥 Скачано {downloaded_size} байт в {tmp_path}")
            if downloaded_size == 0:
                raise Exception(f"Скачанный файл пуст, ожидалось {info.size} байт")

            # Генерируем карточки
            flashcards = self.qa_service.process_pdf(tmp_path, max_cards)

            # Сохраняем карточки
            pdf_repo.save_flashcards(file_id, user_id, flashcards)

            # Обновляем статус
            pdf_repo.update_status(file_id, ProcessingStatus.PROCESSED)

            # Логирование в историю
            history_repo.add_action(
                user_id=user_id,
                action="process",
                details=f"Обработано {len(flashcards)} карточек",
                filename=filename
            )

            # Логирование в ActionLog
            action_log_repo.create(
                user_id=user_id,
                file_id=file_id,
                action=ActionType.GENERATE_CARDS,
                details={"count": len(flashcards)}
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
        pdf_file = self.pdf_repo.get_pdf_by_id(file_id)
        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Проверка прав: владелец или админ
        if user.role != UserRole.admin and pdf_file.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Not enough permissions")

        try:
            url = generate_presigned_url(MINIO_BUCKET_PDF, pdf_file.file_key, expires=3600)
        except Exception as e:
            print(f"Ошибка генерации pre-signed URL для файла {file_id}: {e}")
            raise HTTPException(status_code=500, detail="Не удалось сгенерировать ссылку для скачивания")

        # Логирование
        self.action_log_repo.create(
            user_id=user.user_id,
            file_id=file_id,
            action=ActionType.DOWNLOAD,
            details={"url_expires_in": 3600}
        )

        return {"download_url": url}

    def list_pdfs_filtered(
        self,
        user: User,
        page: int = 1,
        limit: int = 10,
        status: Optional[ProcessingStatus] = None,
        search: Optional[str] = None,
        sort: str = "created_at_desc"
    ) -> Dict[str, Any]:
        query = self.db.query(PDFFile).filter(PDFFile.is_deleted == False)

        # Ограничение по роли
        if user.role == UserRole.admin:
            # Админ видит все файлы, поиск по имени файла или email владельца
            if search:
                query = query.join(User).filter(
                    or_(
                        PDFFile.file_name.ilike(f"%{search}%"),
                        User.email.ilike(f"%{search}%")
                    )
                )
        else:
            # Обычный пользователь видит только свои
            query = query.filter(PDFFile.user_id == user.user_id)
            if search:
                query = query.filter(PDFFile.file_name.ilike(f"%{search}%"))

        # Фильтр по статусу
        if status:
            query = query.filter(PDFFile.status == status)

        # Сортировка
        if sort == "created_at_desc":
            query = query.order_by(PDFFile.created_at.desc())
        elif sort == "created_at_asc":
            query = query.order_by(PDFFile.created_at.asc())
        elif sort == "name_asc":
            query = query.order_by(PDFFile.file_name.asc())
        elif sort == "name_desc":
            query = query.order_by(PDFFile.file_name.desc())

        # Пагинация
        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()

        # Формируем результат
        result = []
        for pdf in items:
            pdf_dict = {
                "id": pdf.id,
                "file_name": pdf.file_name,
                "size": pdf.size,
                "status": pdf.status.value,
                "created_at": pdf.created_at.isoformat() if pdf.created_at else None,
                "owner_id": pdf.user_id,
            }
            if user.role == UserRole.admin:
                pdf_dict["owner_email"] = pdf.user.email
            result.append(pdf_dict)

        return {
            "success": True,
            "items": result,
            "total": total,
            "page": page,
            "limit": limit
        }

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
            "cards": [
                {
                    "id": c.id,
                    "question": c.question,
                    "answer": c.answer,
                    "context": c.context,
                    "source": c.source,
                    "is_hidden": c.is_hidden,
                    "is_deleted": c.is_deleted,
                    "created_at": c.created_at.isoformat() if c.created_at else None
                } for c in cards
            ],
            "total": total
        }

    def delete_pdf(self, file_id: int, user: User) -> Dict[str, Any]:
        pdf_file = self.pdf_repo.get_pdf_by_id(file_id)
        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Проверка прав: только владелец (админ не может удалять чужие)
        if pdf_file.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Only owner can delete this file")

        # Удаление из MinIO
        delete_file_from_minio(MINIO_BUCKET_PDF, pdf_file.file_key)

        # Мягкое удаление в БД
        self.pdf_repo.soft_delete_pdf(file_id)

        # Логирование в историю
        self.history_repo.add_action(
            user_id=user.user_id,
            action="delete",
            details="Файл удалён",
            filename=pdf_file.file_name
        )

        # Логирование в ActionLog
        self.action_log_repo.create(
            user_id=user.user_id,
            file_id=file_id,
            action=ActionType.DELETE,
            details={"filename": pdf_file.file_name}
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