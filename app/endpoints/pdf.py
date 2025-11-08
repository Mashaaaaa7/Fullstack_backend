from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PDFFile, User
from app.auth import get_current_user
from datetime import datetime
import tempfile
import os

router = APIRouter()

# ✅ Сохранение PDF в БД
@router.post("/upload-pdf")
async def upload_pdf(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)  # Указываем тип User
):
    try:
        content = await file.read()

        pdf_file = PDFFile(
            file_name=file.filename,
            user_id=current_user.user_id,  # ✅ Через точку
            created_at=datetime.now(),
            file_size=len(content),
            file_path=None
        )

        db.add(pdf_file)
        db.commit()
        db.refresh(pdf_file)

        return {
            "success": True,
            "file_name": file.filename,
            "file_id": pdf_file.id,
            "message": "File uploaded successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        files = db.query(PDFFile).filter(
            PDFFile.user_id == current_user.user_id
        ).order_by(PDFFile.created_at.desc()).all()

        return {
            "success": True,
            "history": [
                {
                    "id": f.id,
                    "filename": f.file_name,
                    "upload_date": f.created_at.isoformat(),
                    "file_size": f.file_size
                }
                for f in files
            ],
            "total": len(files)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Генерация карточек через AI
@router.post("/process-pdf", summary="Генерация карточек через AI")
async def process_pdf(file: UploadFile = File(...)):
    """
    Генерирует учебные карточки из PDF через обученную AI модель.
    """

    from app.main import qa_generator

    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Разрешены только PDF файлы")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(await file.read())
            tmp_path = tmp_file.name

        cards = qa_generator.process_pdf(tmp_path, max_cards=10)
        os.unlink(tmp_path)

        if not cards:
            raise HTTPException(status_code=400, detail="Не удалось сгенерировать карточки")

        return {
            "success": True,
            "cards": cards,
            "total": len(cards),
            "filename": file.filename
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# ✅ История загрузок
@router.get("/history", summary="История загрузок")
async def get_history(
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
):
    """Возвращает историю загрузок пользователя"""

    try:
        files = db.query(PDFFile).filter(
            PDFFile.user_id == current_user["sub"]
        ).order_by(PDFFile.created_at.desc()).all()

        return {
            "success": True,
            "history": [
                {
                    "id": f.id,
                    "filename": f.file_name,
                    "upload_date": f.created_at.isoformat(),
                    "file_size": f.file_size
                }
                for f in files
            ],
            "total": len(files)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))