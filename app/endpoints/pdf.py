from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
import os
import sys
import logging
from app.auth import get_current_user
from app.models import User, PDFFile
from app.database import SessionLocal, get_db
from app import crud, models
from app.services.qa_generator import QAPair, load_qg_model

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# ✅ STARTUP - Загружаем QA модель при старте
# ============================================================================
@router.on_event("startup")
async def startup_event():
    """Загружает QA модель при старте приложения"""
    logger.info("🚀 Инициализация QA модели...")
    load_qg_model()
    logger.info("✓ QA модель готова к работе")


# ============================================================================
# ✅ ENDPOINT 1: Upload PDF
# ============================================================================
@router.post("/upload-pdf")
async def upload_pdf(
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Загружает PDF файл"""
    try:
        folder = f"uploads/{user.user_id}/"
        os.makedirs(folder, exist_ok=True)

        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(folder, unique_filename)

        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        db_file = PDFFile(
            file_name=file.filename,
            file_path=file_path,
            user_id=user.user_id
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        try:
            crud.add_action(
                db=db,
                action="upload",
                filename=file.filename,
                details=f"Uploaded {len(contents)} bytes",
                user_id=user.user_id
            )
        except Exception as e:
            logger.warning(f"Action not logged: {e}")

        return {
            "file_name": file.filename,
            "file_id": db_file.id,
            "message": "File uploaded successfully"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ✅ BACKGROUND FUNCTION - Обработка PDF в фоне
# ============================================================================
def process_pdf_background(
        file_id: int,
        file_path: str,
        filename: str,
        user_id: int,
        max_cards: int,
        status_id: int
):
    """Генерирует карточки в фоне и обновляет статус"""
    db = SessionLocal()
    try:
        logger.info(f"🔄 Начинаю обработку {filename}...")
        print(f"🔄 Начинаю обработку {filename}...", flush=True)

        # Инициализируем QA генератор
        qa_gen = QAPair()

        # Обрабатываем PDF
        flashcards = qa_gen.process_pdf(file_path, max_cards)

        if not flashcards:
            logger.warning(f"⚠️ Не удалось сгенерировать карточки для {filename}")
            flashcards = []

        # Сохраняем карточки в БД
        crud.save_flashcards(db, file_id, user_id, flashcards)

        # Обновляем статус на "completed"
        status = db.query(models.ProcessingStatus).filter(
            models.ProcessingStatus.id == status_id
        ).first()
        if status:
            status.status = "completed"
            status.cards_count = len(flashcards)
            db.commit()

        # Логируем действие
        crud.add_action(
            db=db,
            action="process",
            filename=filename,
            details=f"Created {len(flashcards)} flashcards",
            user_id=user_id
        )

        logger.info(f"✅ Карточки для {filename} готовы! Создано: {len(flashcards)}")
        print(f"✅ Карточки для {filename} готовы! Создано: {len(flashcards)}", flush=True)

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке {filename}: {e}")
        print(f"❌ Ошибка при обработке {filename}: {e}", flush=True)

        # Обновляем статус на "failed"
        try:
            status = db.query(models.ProcessingStatus).filter(
                models.ProcessingStatus.id == status_id
            ).first()
            if status:
                status.status = "failed"
                db.commit()
        except Exception as e2:
            logger.error(f"❌ Не смог обновить статус: {e2}")

    finally:
        db.close()


# ============================================================================
# ✅ ENDPOINT 2: START PROCESSING
# ============================================================================
@router.post("/process-pdf/{file_id}")
async def process_pdf(
        file_id: int,
        max_cards: int = Query(10, ge=1, le=100),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Запускает обработку PDF в фоне"""
    try:
        # Проверяем, что файл существует и принадлежит пользователю
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        if not os.path.exists(pdf_file.file_path):
            raise HTTPException(status_code=404, detail="File deleted or moved")

        # Создаём запись о статусе обработки
        status_record = models.ProcessingStatus(
            pdf_file_id=file_id,
            user_id=user.user_id,
            status="processing"
        )
        db.add(status_record)
        db.commit()
        db.refresh(status_record)

        # Добавляем фоновую задачу
        background_tasks.add_task(
            process_pdf_background,
            file_id=file_id,
            file_path=pdf_file.file_path,
            filename=pdf_file.file_name,
            user_id=user.user_id,
            max_cards=max_cards,
            status_id=status_record.id
        )

        return {
            "file_id": file_id,
            "message": "🔄 Генерация карточек началась в фоне",
            "status": "processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске обработки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ✅ ENDPOINT 3: Get Processing Status
# ============================================================================
@router.get("/processing-status/{file_id}")
async def check_processing_status(
        file_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Проверяет статус обработки PDF"""
    try:
        # Проверяем, что файл принадлежит пользователю
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Получаем последний статус обработки
        status = db.query(models.ProcessingStatus).filter(
            models.ProcessingStatus.pdf_file_id == file_id,
            models.ProcessingStatus.user_id == user.user_id
        ).order_by(models.ProcessingStatus.created_at.desc()).first()

        if not status:
            return {
                "success": True,
                "status": "not_started",
                "cards_count": 0
            }

        return {
            "success": True,
            "status": status.status,  # "processing", "completed", "failed"
            "cards_count": status.cards_count or 0,
            "created_at": status.created_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ✅ ENDPOINT 4: Get Generated Cards
# ============================================================================
@router.get("/cards/{file_id}")
async def get_cards(
        file_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получает сгенерированные карточки"""
    try:
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        flashcards = crud.get_flashcards_by_pdf(db, file_id, user.user_id)

        return {
            "success": True,
            "file_name": pdf_file.file_name,
            "cards": [
                {
                    "id": card.id,
                    "question": card.question,
                    "answer": card.answer,
                    "context": card.context,
                    "source": card.source,
                    "created_at": card.created_at.isoformat() if card.created_at else None
                }
                for card in flashcards
            ],
            "total": len(flashcards)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ✅ ENDPOINT 5: List User's PDFs
# ============================================================================
@router.get("/pdfs")
async def list_user_pdfs(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получает активные PDF пользователя"""
    try:
        pdf_files = db.query(PDFFile).filter(
            PDFFile.user_id == user.user_id,
            PDFFile.is_deleted == False
        ).all()

        return {
            "success": True,
            "pdfs": [
                {
                    "id": pdf.id,
                    "name": pdf.file_name,
                    "file_size": os.path.getsize(pdf.file_path) if os.path.exists(pdf.file_path) else 0
                }
                for pdf in pdf_files
            ],
            "total": len(pdf_files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ✅ ENDPOINT 6: Get Action History
# ============================================================================
@router.get("/history")
async def get_history(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получает историю действий пользователя"""
    try:
        actions = crud.get_history(db, user.user_id)
        history_data = [
            {
                "id": action.id,
                "action": action.action,
                "filename": action.filename or "unknown",
                "created_at": action.created_at.isoformat(),
                "details": action.details or f"{action.action} file",
                "timestamp": action.created_at.isoformat()
            }
            for action in actions
        ]
        return {
            "success": True,
            "history": history_data,
            "total": len(history_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ✅ ENDPOINT 7: Delete PDF and Cards
# ============================================================================
@router.delete("/delete-file/{file_id}")
async def delete_pdf(
        file_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Мягкое удаление файла - помечает как удалённый"""
    try:
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id,
            PDFFile.is_deleted == False
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Помечаем как удалённый
        pdf_file.is_deleted = True
        db.commit()

        logger.info(f"🗑️ File {pdf_file.file_name} marked as deleted")

        return {
            "success": True,
            "message": f"File {pdf_file.file_name} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ ERROR in delete_pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))