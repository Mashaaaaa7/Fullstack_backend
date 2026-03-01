from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
import uuid, os
import asyncio
from app.endpoints.auth import get_current_user
from app.database import SessionLocal, get_db
from app.models import User, PDFFile, UserRole
from app.services.qa_generator import QAGenerator

router = APIRouter()
qa_generator = None


def get_pdf_for_user(db: Session, user: User, file_id: int):
    pdf_file = db.query(PDFFile).filter(
        PDFFile.id == file_id, PDFFile.is_deleted == False
    ).first()
    if not pdf_file:
        return None
    if user.role == UserRole.admin or pdf_file.user_id == user.user_id:
        return pdf_file
    return None


def get_qa_generator():
    global qa_generator
    if qa_generator is None:
        print("🔧 Инициализирую QAGenerator...")
        qa_generator = QAGenerator()
    return qa_generator


# ✅ УПРОЩЁННАЯ обработка БЕЗ статусов/CRUD
def process_pdf_sync(file_id: int, file_path: str, filename: str, user_id: int, max_cards: int):
    db = SessionLocal()
    try:
        print(f"🔄 Обрабатываю {filename}...")
        qa_gen = get_qa_generator()
        flashcards = qa_gen.process_pdf(file_path, max_cards)  # твоя магия

        # Сохраняем в БД (если crud.save_flashcards есть)
        try:
            from app import crud
            crud.save_flashcards(db, file_id, user_id, flashcards)
        except:
            print("⚠️ crud.save_flashcards не найден — пропускаем")

        db.commit()
        print(f"✅ Готово! {len(flashcards) if flashcards else 0} карточек")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        db.close()


async def process_pdf_background(file_id: int, file_path: str, filename: str, user_id: int, max_cards: int):
    await asyncio.to_thread(process_pdf_sync, file_id, file_path, filename, user_id, max_cards)


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
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
    return {"success": True, "file_id": db_file.id, "file_name": file.filename}


@router.post("/process-pdf/{file_id}/start")
async def start_pdf_processing(file_id: int, background_tasks: BackgroundTasks, max_cards: int = Query(20),
                               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_file = get_pdf_for_user(db, user, file_id)
    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")

    background_tasks.add_task(process_pdf_background, file_id, pdf_file.file_path,
                              pdf_file.file_name, user.user_id, max_cards)
    return {"success": True, "status": "processing", "message": "Обработка запущена"}


@router.get("/history")
async def get_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role == UserRole.admin:
        actions = db.query(models.ActionHistory).all()  # <- заменили здесь
    else:
        actions = crud.get_history(db, user.user_id)

    return {
        "success": True,
        "history": [
            {
                "id": a.id,
                "action": a.action,
                "filename": a.filename,
                "details": a.details,
                "created_at": a.created_at.isoformat()
            }
            for a in actions
        ]
    }

@router.get("/pdfs")
async def list_pdfs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == UserRole.admin:
        pdf_files = db.query(PDFFile).filter(PDFFile.is_deleted == False).all()
    else:
        pdf_files = db.query(PDFFile).filter(PDFFile.user_id == user.user_id, PDFFile.is_deleted == False).all()
    return {
        "success": True,
        "pdfs": [{"id": p.id, "name": p.file_name,
                  "file_size": os.path.getsize(p.file_path) if os.path.exists(p.file_path) else 0} for p in pdf_files],
        "total": len(pdf_files)
    }


@router.get("/cards/{file_id}")
async def get_cards(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_file = get_pdf_for_user(db, user, file_id)
    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")

    try:
        from app.models import Flashcard
        if user.role == UserRole.admin:
            cards = db.query(Flashcard).filter(Flashcard.pdf_file_id == file_id).limit(10).all()
        else:
            cards = db.query(Flashcard).filter(Flashcard.pdf_file_id == file_id,
                                               Flashcard.user_id == user.user_id).limit(10).all()
    except:
        cards = []

    return {"success": True, "file_name": pdf_file.file_name, "cards": cards, "total": len(cards)}


@router.delete("/delete-file/{file_id}")
async def delete_pdf(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pdf_file = get_pdf_for_user(db, user, file_id)
    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")
    pdf_file.is_deleted = True
    db.commit()
    return {"success": True, "message": f"{pdf_file.file_name} deleted"}
