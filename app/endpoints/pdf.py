from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
import os
import uuid
import sys
from concurrent.futures import ThreadPoolExecutor

from app.auth import get_current_user
from app.models import User, PDFFile
from app.database import SessionLocal, get_db
from app import crud
from app.services.qa_generator import QAGenerator

router = APIRouter()
qa_generator = None
executor = ThreadPoolExecutor(max_workers=2)

def get_qa_generator():
    global qa_generator
    if qa_generator is None:
        print("🔧 Инициализирую QAGenerator...", flush=True)
        sys.stdout.flush()
        qa_generator = QAGenerator()
    return qa_generator

@router.post("/upload-pdf")
async def upload_pdf(
        file: UploadFile = File(...),
        user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        folder = f"uploads/{user.user_id}/"
        os.makedirs(folder, exist_ok=True)

        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(folder, unique_filename)

        # 1. Асинхронно читаем файл
        contents = await file.read()

        # 2. Синхронно пишем на диск (быстро)
        with open(file_path, "wb") as f:
            f.write(contents)

        # 3. Добавляем в БД
        db_file = PDFFile(
            file_name=file.filename,
            file_path=file_path,
            user_id=user.user_id
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        # 4. Логируем в фоне (не блокируя ответ)
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
    try:
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail=f"PDF file with ID {file_id} not found")

        if not os.path.exists(pdf_file.file_path):
            raise HTTPException(status_code=404, detail="File deleted from disk")

        # Запускаем обработку в фоне
        background_tasks.add_task(
            process_pdf_background,
            file_id=file_id,
            file_path=pdf_file.file_path,
            filename=pdf_file.file_name,
            user_id=user.user_id,
            max_cards=max_cards
        )

        # Сразу возвращаем ответ (не ждём обработки)
        return {
            "file_id": file_id,
            "message": "🔄 Генерация карточек началась. Проверьте результат через /api/pdf/cards/{file_id}",
            "status": "processing"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def process_pdf_background(file_id: int, file_path: str, filename: str, user_id: int, max_cards: int):
    """Генерирует карточки в фоне"""
    db = SessionLocal()
    try:
        qa_gen = get_qa_generator()
        flashcards = qa_gen.process_pdf(file_path, max_cards)

        # Логируем результат
        crud.add_action(
            db=db,
            action="process",
            filename=filename,
            details=f"Created {len(flashcards)} flashcards",
            user_id=user_id
        )
        print(f"✅ Карточки для {filename} готовы! Создано: {len(flashcards)}")
    except Exception as e:
        print(f"❌ Ошибка при обработке {filename}: {e}")
    finally:
        db.close()


@router.get("/cards/{file_id}")
async def get_cards(
        file_id: int,
        max_cards: int = Query(10, ge=1, le=100),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получить карточки (кеш результата или генерировать если ещё нет)"""
    try:
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        qa_gen = get_qa_generator()
        flashcards = qa_gen.process_pdf(pdf_file.file_path, max_cards)

        return {
            "success": True,
            "file_name": pdf_file.file_name,
            "cards": flashcards,
            "total": len(flashcards)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        actions = crud.get_history(db, user.user_id)
        history_data = [
            {
                "id": action.id,
                "action": action.action,
                "filename": action.filename or "unknown",
                "created_at": action.created_at.isoformat(),
                "details": action.details or f"{action.action} file"
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


@router.delete("/delete-file/{file_id}")
async def delete_pdf(
        file_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        pdf_file = db.query(PDFFile).filter(
            PDFFile.id == file_id,
            PDFFile.user_id == user.user_id
        ).first()

        if not pdf_file:
            raise HTTPException(status_code=404, detail="PDF not found")

        if os.path.exists(pdf_file.file_path):
            os.remove(pdf_file.file_path)

        db.delete(pdf_file)
        db.commit()

        crud.add_action(
            db=db,
            action="delete",
            filename=pdf_file.file_name,
            details=f"Deleted file {pdf_file.file_name}",
            user_id=user.user_id
        )

        return {
            "success": True,
            "message": f"File {pdf_file.file_name} deleted"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))