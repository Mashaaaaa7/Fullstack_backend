from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, Query, Request
from typing import Optional

from app.core.dependencies import get_db, get_current_user
from app.schemas.pdf import (
    PDFUploadResponse, PDFProcessingResponse, CardsResponse, DeleteResponse, HistoryResponse
)
from app.models import User, ProcessingStatus
from app.services.pdf_service import PDFService
from app.services.qa_generator_service import QAGeneratorService

router = APIRouter()


def get_pdf_service(
    request: Request,
    db=Depends(get_db)
) -> PDFService:
    qa_service: QAGeneratorService = request.app.state.qa_service
    return PDFService(db, qa_service)

@router.post("/upload", response_model=PDFUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    service: PDFService = Depends(get_pdf_service),
    user: User = Depends(get_current_user)
):
    return await service.upload_pdf(file, user)


@router.get("/list", response_model=dict)
def list_pdfs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[ProcessingStatus] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    sort: str = Query("created_at_desc", pattern="^(created_at_desc|created_at_asc|name_asc|name_desc)$"),
    service: PDFService = Depends(get_pdf_service),
    user: User = Depends(get_current_user)
):
    return service.list_pdfs_filtered(
        user=user, page=page, limit=limit,
        status=status, search=search, sort=sort
    )


@router.get("/history", response_model=HistoryResponse)
def get_history(
    limit: int = Query(50, ge=1, le=200),
    service: PDFService = Depends(get_pdf_service),
    user: User = Depends(get_current_user)
):
    return service.get_history(user, limit)


@router.get("/cards/{file_id}", response_model=CardsResponse)
def get_cards(
    file_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    service: PDFService = Depends(get_pdf_service),
    user: User = Depends(get_current_user)
):
    return service.get_cards(file_id, user, skip, limit)


# ✅ Динамические роуты — НИЖЕ статичных
@router.post("/{file_id}/process", response_model=PDFProcessingResponse)
def start_processing(
    file_id: int,
    background_tasks: BackgroundTasks,
    max_cards: int = Query(20, ge=1, le=100),
    service: PDFService = Depends(get_pdf_service),
    user: User = Depends(get_current_user)
):
    pdf_file = service.start_processing(file_id, user, max_cards)
    background_tasks.add_task(
        service.process_pdf_sync,
        file_id,
        pdf_file.file_key,
        pdf_file.file_name,
        user.user_id,
        max_cards
    )
    return {"success": True, "status": "processing", "message": "Обработка запущена"}


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    service: PDFService = Depends(get_pdf_service),
    user: User = Depends(get_current_user)
):
    return service.get_download_url(file_id, user)


@router.delete("/{file_id}", response_model=DeleteResponse)
def delete_pdf(
    file_id: int,
    service: PDFService = Depends(get_pdf_service),
    user: User = Depends(get_current_user)
):
    return service.delete_pdf(file_id, user)