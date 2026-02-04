from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
from app.auth import get_current_user
from app.models import User, PDFFile
from app.database import SessionLocal, get_db
from app import crud, models
import os
import sys
from app.services.qa_generator import QAGenerator

router = APIRouter()
qa_generator = None

def get_qa_generator():
    global qa_generator
    if qa_generator is None:
        print("🔧 Инициализирую QAGenerator...", flush=True)
        sys.stdout.flush()
        qa_generator = QAGenerator()
    return qa_generator

# ENDPOINT 1: Upload PDF
@router.post("/upload-pdf")
async def upload_pdf(
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
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
            print(f"Warning: action not logged: {e}")

        return {
            "file_name": file.filename,
            "file_id": db_file.id,
            "message": "File uploaded successfully"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

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
        print(f"🔄 Начинаю обработку {filename}...", flush=True)

        qa_gen = get_qa_generator()
        flashcards = qa_gen.process_pdf(file_path, max_cards)

        crud.save_flashcards(db, file_id, user_id, flashcards)

        status = db.query(models.ProcessingStatus).filter(
            models.ProcessingStatus.id == status_id
        ).first()
        if status:
            status.status = "completed"
            status.cards_count = len(flashcards)
            db.commit()

        crud.add_action(
            db=db,
            action="process",
            filename=filename,
            details=f"Created {len(flashcards)} flashcards",
            user_id=user_id
        )

        print(f"✅ Карточки для {filename} готовы! Создано: {len(flashcards)}", flush=True)

    except Exception as e:
        print(f"❌ Ошибка при обработке {filename}: {e}", flush=True)

        try:
            status = db.query(models.ProcessingStatus).filter(
                models.ProcessingStatus.id == status_id
            ).first()
            if status:
                status.status = "failed"
                db.commit()
        except Exception as e2:
            print(f"❌ Не смог обновить статус: {e2}")

    finally:
        db.close()

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
        raise  # Re-raise HTTPException
    except Exception as e:
        print(f"❌ Ошибка при запуске обработки: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

@router.get("/cards/{file_id}")
async def get_cards(
    file_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получает сгенерированные карточки с пагинацией"""
    try:
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Получаем всего карточек (для расчета общего количества)
        total = db.query(models.Flashcard).filter(
            models.Flashcard.pdf_file_id == file_id,
            models.Flashcard.user_id == user.user_id
        ).count()

        # Получаем карточки с пагинацией
        flashcards = db.query(models.Flashcard).filter(
            models.Flashcard.pdf_file_id == file_id,
            models.Flashcard.user_id == user.user_id
        ).offset(skip).limit(limit).all()

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
            "total": total,
            "skip": skip,
            "limit": limit,
            "pages": (total + limit - 1) // limit  # Количество страниц
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pdfs")
async def list_user_pdfs(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получает активные PDF """
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


# ENDPOINT 7: Delete PDF and Cards
@router.delete("/delete-file/{file_id}")
async def delete_pdf(
        file_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """помечает как удалённый, БД не трогаем"""
    try:
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id,
            PDFFile.is_deleted == False
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        # Помечаем как удалённый (НЕ удаляем из БД!)
        pdf_file.is_deleted = True
        db.commit()

        print(f"🗑️ File {pdf_file.file_name} marked as deleted (is_deleted=True)")

        return {
            "success": True,
            "message": f"File {pdf_file.file_name} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR in delete_pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))