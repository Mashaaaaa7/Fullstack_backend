from contextlib import asynccontextmanager
from app.minio_client import ensure_bucket, MINIO_BUCKET_PDF
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base
from app.services.qa_generator_service import QAGeneratorService
from app.endpoints import auth, profile, pdf, admin
from app.routers import dictionary, seo, landing


Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app):
    # Инициализация при старте сервера
    ensure_bucket(MINIO_BUCKET_PDF)
    qa = QAGeneratorService()
    await asyncio.to_thread(qa._initialize)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router,prefix="/api/profile", tags=["profile"])
app.include_router(pdf.router, prefix="/api/pdf",  tags=["pdf"])
app.include_router(dictionary.router, prefix="/api/dictionary", tags=["dictionary"])
app.include_router(seo.router, tags=["seo"])
app.include_router(landing.router, tags=["landing"])

app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/")
def root():
    return {"message": "API работает"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}