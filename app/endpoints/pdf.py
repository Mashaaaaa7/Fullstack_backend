from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import os
import uuid
import sys

from app.auth import get_current_user
from app.models import User, PDFFile
from app.database import SessionLocal, get_db
from app import crud
router = APIRouter()
qa_generator = None

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

        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        db_file = crud.add_pdf(
            db=db,
            file_name=file.filename,
            file_path=file_path,
            user_id=user.user_id
        )

        crud.add_action(
            db=db,
            action="upload",
            filename=file.filename,
            details=f"Загружен файл {file.filename}",
            user_id=user.user_id
        )

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
        db: Session = Depends(get_db)
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

        qa_gen = get_qa_generator()
        flashcards = qa_gen.process_pdf(pdf_file.file_path, max_cards)

        crud.add_action(
            db=db,
            action="process",
            filename=pdf_file.file_name,
            details=f"Created {len(flashcards)} flashcards",
            user_id=user.user_id
        )

        return {
            "file_name": pdf_file.file_name,
            "file_id": file_id,
            "cards_generated": len(flashcards),
            "flashcards": flashcards,
            "message": f"Successfully created {len(flashcards)} flashcards"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cards/{file_id}")
async def get_cards(
        file_id: int,
        max_cards: int = Query(10, ge=1, le=100),
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

        qa_gen = get_qa_generator()
        flashcards = qa_gen.process_pdf(pdf_file.file_path, max_cards)

        return {
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
