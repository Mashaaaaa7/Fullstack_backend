from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.minio_client import ensure_bucket, MINIO_BUCKET_PDF
from app.services.qa_generator_service import QAGeneratorService
from app.endpoints import auth, profile, pdf, admin
from app.routers import dictionary, seo, landing


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_bucket(MINIO_BUCKET_PDF)
    except Exception as e:
        print(f"⚠️ MinIO недоступен: {e}")

    qa = QAGeneratorService()
    try:
        await asyncio.to_thread(qa._initialize)
    except Exception as e:
        print(f"⚠️ QAGenerator не инициализирован: {e}")

    app.state.qa_service = qa
    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(pdf.router, prefix="/api/pdf", tags=["pdf"])
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