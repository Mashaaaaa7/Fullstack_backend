from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models import Base


class PDFFile(Base):
    __tablename__ = "pdf_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("user.user_id"))

    user = relationship("User", back_populates="pdf_files")

class ActionHistory(Base):
    __tablename__ = "action_history"

    id = Column(Integer, primary_key=True)
    action = Column(String(100), nullable=False)
    filename = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)  # ← ДОБАВЬ ЭТУ СТРОКУ
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="action_history")


    #