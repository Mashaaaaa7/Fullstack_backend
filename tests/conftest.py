import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

@pytest.fixture(autouse=True)
def mock_qa_service():
    # Patch where it's USED (pdf_service), not where it's defined
    with patch("app.services.pdf_service.QAGeneratorService") as mock_cls:
        mock_cls.return_value = MagicMock()
        yield mock_cls


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_credentials():
    return {
        "email": "mashavacylieva@gmail.com",
        "password": "Mary2004"
    }


@pytest.fixture
def admin_credentials():
    return {
        "email": "mary200438@gmail.com",
        "password": "Mary2004"
    }


@pytest.fixture
def user_token(client, user_credentials):
    res = client.post("/api/auth/login", json=user_credentials)
    return res.json()["access_token"]


@pytest.fixture
def admin_token(client, admin_credentials):
    res = client.post("/api/auth/login", json=admin_credentials)
    return res.json()["access_token"]