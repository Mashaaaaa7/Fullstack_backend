from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.services.pdf_service import PDFService
from app.schemas.pdf import (
    PDFUploadResponse, PDFProcessingResponse, PDFListResponse,
    CardsResponse, DeleteResponse, HistoryResponse
)
from app.models import User

router = APIRouter()

@router.post("/upload-pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PDFService(db)
    return await service.upload_pdf(file, user)

@router.post("/process-pdf/{file_id}/start", response_model=PDFProcessingResponse)
def start_pdf_processing(
    file_id: int,
    background_tasks: BackgroundTasks,
    max_cards: int = Query(20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PDFService(db)
    pdf_file = service.start_processing(file_id, user, max_cards)
    background_tasks.add_task(
        service.process_pdf_sync,
        file_id,
        pdf_file.file_path,
        pdf_file.file_name,
        user.user_id,
        max_cards
    )
    return {"success": True, "status": "processing", "message": "Обработка запущена"}

@router.get("/pdfs", response_model=PDFListResponse)
def list_pdfs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PDFService(db)
    return service.list_pdfs(user)

@router.get("/cards/{file_id}", response_model=CardsResponse)
def get_cards(
    file_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PDFService(db)
    return service.get_cards(file_id, user, skip, limit)

@router.delete("/delete-file/{file_id}", response_model=DeleteResponse)
def delete_pdf(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PDFService(db)
    return service.delete_pdf(file_id, user)

@router.get("/history", response_model=HistoryResponse)
def get_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PDFService(db)
    return service.get_history(user)