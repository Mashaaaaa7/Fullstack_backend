import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # ← сначала это

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app

sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture(autouse=True)
def mock_minio():
    with patch("app.services.pdf_service.upload_file_to_minio") as mock_upload, \
         patch("app.services.pdf_service.delete_file_from_minio") as mock_delete, \
         patch("app.services.pdf_service.generate_presigned_url", return_value="http://mock/file.pdf"):
        mock_upload.return_value = "mock-file-key.pdf"
        mock_delete.return_value = None
        yield

@pytest.fixture(autouse=True)
def mock_qa_service():
    from app.services.qa_generator_service import QAGeneratorService
    QAGeneratorService._instance = None

    with patch("app.services.pdf_service.QAGeneratorService") as mock_cls:
        mock_cls.return_value = MagicMock()
        yield mock_cls

    QAGeneratorService._instance = None

@pytest.fixture(autouse=True)
def db_rollback():
    session = SessionLocal()
    session.begin_nested()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def user_credentials():
    return {"email": "mashavacylieva@gmail.com", "password": "Mary2004"}

@pytest.fixture
def admin_credentials():
    return {"email": "mary200438@gmail.com", "password": "Mary2004"}

@pytest.fixture
def user_token(client, user_credentials):
    res = client.post("/api/auth/login", json=user_credentials)
    return res.json()["access_token"]

@pytest.fixture
def admin_token(client, admin_credentials):
    res = client.post("/api/auth/login", json=admin_credentials)
    return res.json()["access_token"]

#