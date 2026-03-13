from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum
import enum
import uuid
from sqlalchemy import JSON

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# Московское время (UTC+3)
MSK = timezone(timedelta(hours=3))
def get_msk_time():
    return datetime.now(MSK)

class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    pdf_files = relationship("PDFFile", back_populates="user", cascade="all, delete-orphan")
    flashcards = relationship("Flashcard", back_populates="user", cascade="all, delete-orphan")
    action_history = relationship("ActionHistory", back_populates="user", cascade="all, delete-orphan")

class ProcessingStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class ActionType(str, enum.Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DELETE = "delete"
    EDIT = "edit"
    GENERATE_CARDS = "generate_cards"

class PDFFile(Base):
    __tablename__ = "pdf_files"
    id = Column(Integer, primary_key=True)
    file_name = Column(String(255), nullable=False)  # оригинальное имя
    file_key = Column(String(500), unique=True, nullable=False)  # ключ в MinIO (вместо file_path)
    size = Column(Integer, nullable=False)  # размер в байтах
    mime_type = Column(String(100), nullable=False)  # application/pdf
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.UPLOADED, nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True, nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_msk_time)
    updated_at = Column(DateTime, default=get_msk_time, onupdate=get_msk_time)  # для сортировки

    user = relationship("User", back_populates="pdf_files")
    flashcards = relationship("Flashcard", back_populates="pdf_file", cascade="all, delete-orphan")
    action_logs = relationship("ActionLog", back_populates="pdf_file", cascade="all, delete-orphan")  # добавим позже

class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey('pdf_files.id'), nullable=False, index=True)
    action = Column(Enum(ActionType), nullable=False)
    details = Column(JSON, nullable=True)  # дополнительная информация
    timestamp = Column(DateTime, default=get_msk_time)

    user = relationship("User", back_populates="action_logs")
    pdf_file = relationship("PDFFile", back_populates="action_logs")


class Flashcard(Base):
    __tablename__ = "flashcards"
    id = Column(Integer, primary_key=True)
    pdf_file_id = Column(Integer, ForeignKey('pdf_files.id'), index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    context = Column(Text)
    source = Column(String)
    is_hidden = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_msk_time)

    pdf_file = relationship("PDFFile", back_populates="flashcards")

    user = relationship("User", back_populates="flashcards")

class ActionHistory(Base):
    __tablename__ = "action_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True)
    created_at = Column(DateTime, index=True)
    action = Column(String(100), nullable=False)
    filename = Column(String(255))
    details = Column(Text)

    user = relationship("User", back_populates="action_history")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")