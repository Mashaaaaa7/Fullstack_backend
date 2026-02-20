from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.endpoints import auth, profile, pdf, admin
from app.database import engine
from app.models import Base

# Создаём таблицы (если ещё нет)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS для React на localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(pdf.router, prefix="/api/pdf", tags=["pdf"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/")
def read_root():
    return {"message": "API работает"}
