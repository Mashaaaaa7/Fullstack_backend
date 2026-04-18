import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, UserRole
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    #Создаём таблицы один раз на всю сессию
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables(setup_db):
    #Очищаем данные между тестами — изоляция без пересоздания схемы"
    yield
    session = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture
def db(clean_tables):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


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
    with patch("app.services.pdf_service.QAGeneratorService") as mock_cls, \
         patch("transformers.utils.hub.cached_file"), \
         patch("transformers.safetensors_conversion.auto_conversion"):
        mock_cls.return_value = MagicMock()
        yield mock_cls
    QAGeneratorService._instance = None

@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user_credentials(db):
    user = User(
        email="mashavacylieva@gmail.com",   # тот же email
        hashed_password=get_password_hash("Mary2004"),
        role=UserRole.user
    )
    db.add(user)
    db.commit()
    return {"email": "mashavacylieva@gmail.com", "password": "Mary2004"}


@pytest.fixture
def admin_credentials(db):
    admin = User(
        email="mary200438@gmail.com",
        hashed_password=get_password_hash("Mary2004"),
        role=UserRole.admin
    )
    db.add(admin)
    db.commit()
    return {"email": "mary200438@gmail.com", "password": "Mary2004"}


@pytest.fixture
def user_token(client, user_credentials):
    res = client.post("/api/auth/login", json=user_credentials)
    assert res.status_code == 200, f"Login failed: {res.json()}"
    return res.json()["access_token"]


@pytest.fixture
def admin_token(client, admin_credentials):
    res = client.post("/api/auth/login", json=admin_credentials)
    assert res.status_code == 200, f"Admin login failed: {res.json()}"
    return res.json()["access_token"]