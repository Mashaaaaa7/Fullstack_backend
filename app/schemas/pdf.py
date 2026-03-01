from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class PDFUploadResponse(BaseModel):
    success: bool
    file_id: int
    file_name: str

class PDFProcessingResponse(BaseModel):
    success: bool
    status: str
    message: str

class PDFInfo(BaseModel):
    id: int
    name: str
    file_size: int

class PDFListResponse(BaseModel):
    success: bool
    pdfs: List[PDFInfo]
    total: int

class FlashcardSchema(BaseModel):
    id: int
    question: str
    answer: str
    context: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class CardsResponse(BaseModel):
    success: bool
    file_name: str
    cards: List[FlashcardSchema]
    total: int

class DeleteResponse(BaseModel):
    success: bool
    message: str

class HistoryItem(BaseModel):
    id: int
    action: str
    filename: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime

class HistoryResponse(BaseModel):
    success: bool
    history: List[HistoryItem]