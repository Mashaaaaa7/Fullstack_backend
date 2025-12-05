from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.endpoints import profile, pdf
from app import auth

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

@app.get("/")
def read_root():
    return {"message": "API работает"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
