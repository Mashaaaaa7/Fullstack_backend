from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
from app.auth import get_current_user
from app.models import User, PDFFile
from app.database import SessionLocal, get_db
from app import crud, models
import os
import asyncio
from app.services.qa_generator import QAGenerator

router = APIRouter()
qa_generator = None

def get_qa_generator():
    """Инициализация и кеширование генератора QA"""
    global qa_generator
    if qa_generator is None:
        print("🔧 Инициализирую QAGenerator...", flush=True)
        qa_generator = QAGenerator()
    return qa_generator

def process_pdf_sync(file_id: int, file_path: str, filename: str, user_id: int, max_cards: int, status_id: int):
    """Синхронная обработка PDF (для запуска в отдельном потоке)"""
    db = SessionLocal()
    try:
        print(f"🔄 Начинаю обработку {filename}...", flush=True)
        qa_gen = get_qa_generator()
        flashcards = []
        try:
            flashcards = qa_gen.process_pdf(file_path, max_cards)
        except Exception as e:
            print(f"❌ Ошибка при генерации карточек: {e}", flush=True)

        try:
            crud.save_flashcards(db, file_id, user_id, flashcards)
        except Exception as e:
            print(f"❌ Ошибка при сохранении карточек: {e}", flush=True)

        try:
            status = db.query(models.ProcessingStatus).filter(models.ProcessingStatus.id == status_id).first()
            if status:
                status.status = "completed"
                status.cards_count = len(flashcards)
                db.commit()
        except Exception as e:
            print(f"❌ Не смог обновить статус: {e}", flush=True)

        try:
            crud.add_action(
                db=db,
                action="process",
                filename=filename,
                details=f"Created {len(flashcards)} flashcards",
                user_id=user_id
            )
        except Exception as e:
            print(f"⚠️ Не удалось добавить action в историю: {e}", flush=True)

        print(f"✅ Карточки для {filename} готовы! Создано: {len(flashcards)}", flush=True)

    except Exception as e:
        print(f"❌ Общая ошибка при обработке {filename}: {e}", flush=True)
        try:
            status = db.query(models.ProcessingStatus).filter(models.ProcessingStatus.id == status_id).first()
            if status:
                status.status = "failed"
                status.error_message = str(e)
                db.commit()
        except Exception as e2:
            print(f"❌ Не удалось обновить статус на failed: {e2}")
    finally:
        db.close()

async def process_pdf_background(file_id: int, file_path: str, filename: str, user_id: int, max_cards: int, status_id: int):
    """Асинхронная обертка для фоновой обработки PDF"""
    try:
        await asyncio.to_thread(process_pdf_sync, file_id, file_path, filename, user_id, max_cards, status_id)
    except asyncio.CancelledError:
        print(f"⚠️ Фоновая задача обработки {filename} была отменена", flush=True)

# --- Эндпоинты ---

@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folder = f"uploads/{user.user_id}/"
    os.makedirs(folder, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(folder, unique_filename)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    db_file = PDFFile(file_name=file.filename, file_path=file_path, user_id=user.user_id)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    try:
        crud.add_action(db=db, action="upload", filename=file.filename, details=f"Uploaded {len(contents)} bytes", user_id=user.user_id)
    except Exception as e:
        print(f"⚠️ Warning: action not logged: {e}")

    return {"file_name": file.filename, "file_id": db_file.id, "message": "File uploaded successfully"}

@router.post("/process-pdf/{file_id}/start")
async def start_pdf_processing(file_id: int, max_cards: int = Query(20, ge=1, le=100), background_tasks: BackgroundTasks = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_file = db.query(PDFFile).filter(PDFFile.id == file_id, PDFFile.user_id == user.user_id, PDFFile.is_deleted == False).first()
    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")

    status = models.ProcessingStatus(pdf_file_id=file_id, user_id=user.user_id, status="processing", cards_count=0)
    db.add(status)
    db.commit()
    db.refresh(status)

    background_tasks.add_task(process_pdf_background, file_id=file_id, file_path=pdf_file.file_path, filename=pdf_file.file_name, user_id=user.user_id, max_cards=max_cards, status_id=status.id)

    return {"success": True, "status": "processing", "status_id": status.id, "message": "PDF processing started"}

@router.get("/processing-status/{file_id}")
async def check_processing_status(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_file = db.query(PDFFile).filter(PDFFile.id == file_id, PDFFile.user_id == user.user_id).first()
    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")

    status = db.query(models.ProcessingStatus).filter(models.ProcessingStatus.pdf_file_id == file_id, models.ProcessingStatus.user_id == user.user_id).order_by(models.ProcessingStatus.created_at.desc()).first()

    if not status:
        return {"success": True, "status": "not_started", "cards_count": 0}

    return {"success": True, "status": status.status, "cards_count": status.cards_count or 0, "created_at": status.created_at.isoformat()}

@router.get("/cards/{file_id}")
async def get_cards(file_id: int, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_file = db.query(PDFFile).filter(PDFFile.id == file_id, PDFFile.user_id == user.user_id).first()
    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")

    total = db.query(models.Flashcard).filter(models.Flashcard.pdf_file_id == file_id, models.Flashcard.user_id == user.user_id).count()
    flashcards = db.query(models.Flashcard).filter(models.Flashcard.pdf_file_id == file_id, models.Flashcard.user_id == user.user_id).offset(skip).limit(limit).all()

    return {
        "success": True,
        "file_name": pdf_file.file_name,
        "cards": [{"id": c.id, "question": c.question, "answer": c.answer, "context": c.context, "source": c.source, "created_at": c.created_at.isoformat() if c.created_at else None} for c in flashcards],
        "total": total,
        "skip": skip,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/pdfs")
async def list_user_pdfs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_files = db.query(PDFFile).filter(PDFFile.user_id == user.user_id, PDFFile.is_deleted == False).all()
    return {"success": True, "pdfs": [{"id": p.id, "name": p.file_name, "file_size": os.path.getsize(p.file_path) if os.path.exists(p.file_path) else 0} for p in pdf_files], "total": len(pdf_files)}

@router.get("/history")
async def get_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    actions = crud.get_history(db, user.user_id)
    history_data = [{"id": a.id, "action": a.action, "filename": a.filename or "unknown", "created_at": a.created_at.isoformat(), "details": a.details or f"{a.action} file", "timestamp": a.created_at.isoformat()} for a in actions]
    return {"success": True, "history": history_data, "total": len(history_data)}

@router.delete("/delete-file/{file_id}")
async def delete_pdf(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_file = db.query(PDFFile).filter(PDFFile.id == file_id, PDFFile.user_id == user.user_id, PDFFile.is_deleted == False).first()
    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")

    pdf_file.is_deleted = True
    db.commit()
    print(f"🗑️ File {pdf_file.file_name} marked as deleted (is_deleted=True)")
    return {"success": True, "message": f"File {pdf_file.file_name} deleted"}
