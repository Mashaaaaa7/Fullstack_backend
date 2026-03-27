from app.main import app
import pytest
from fastapi.testclient import TestClient

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