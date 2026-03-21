from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.endpoints import auth, profile, pdf, admin
from app.database import engine
from app.models import Base
from app.routers import dictionary, seo, landing

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(pdf.router, prefix="/api/pdf", tags=["pdf"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(dictionary.router, prefix="/api/dictionary", tags=["dictionary"])
app.include_router(seo.router, tags=["seo"])
app.include_router(landing.router, tags=["landing"])

@app.get("/")
def root():
    return {"message": "API работает"}