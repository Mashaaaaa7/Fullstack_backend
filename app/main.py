from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.model_service import QAGenerator
import os

# ✅ ВАЖНО: Импортируй модели ДО create_all
from app.models import User, PDFFile, ActionHistory

# ✅ Создаем таблицы (теперь SQLAlchemy знает про все модели)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PDF Processing API",
    version="1.0.0",
    description="Генерация учебных карточек из PDF через AI"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация модели
MODEL_PATH = "./app/models/fine_tuned_model"

if os.path.exists(MODEL_PATH):
    print(f"📦 Загрузка обученной модели из {MODEL_PATH}")
    qa_generator = QAGenerator(model_path=MODEL_PATH)
    print("✅ Обученная модель загружена!")
else:
    print("⚠️ Обученная модель не найдена, используется базовая")
    qa_generator = QAGenerator()

# Информация о системе
@app.get("/", tags=["System"])
def read_root():
    return {
        "message": "PDF Processing API",
        "version": "1.0.0",
        "model": "fine-tuned T5"
    }

@app.get("/api/model-info", tags=["System"])
def model_info():
    return {
        "model_type": "fine-tuned" if os.path.exists(MODEL_PATH) else "base",
        "model_path": MODEL_PATH if os.path.exists(MODEL_PATH) else "default",
        "status": "loaded",
        "description": "T5 модель для генерации вопросов из текста"
    }

# Подключение маршрутов
from app.endpoints import pdf, user

app.include_router(user.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(pdf.router, prefix="/api", tags=["File Management"])