import pytest

def test_login_success(client, user_credentials):
    res = client.post("/api/auth", json=user_credentials)

    assert res.status_code == 200
    data = res.json()

    assert "access_token" in data
    assert "refresh_token" in data

def test_login_invalid_password(client, user_credentials):
    res = client.post("/api/auth/login", json={
        "email": user_credentials["email"],
        "password": "wrong"
    })

    assert res.status_code == 401

def test_me_requires_auth(client):
    res = client.get("/api/profile/me")

    assert res.status_code == 401

def test_me_success(client, user_token):
    res = client.get(
        "/api/profile/me",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert res.status_code == 200
    data = res.json()

    assert "email" in data
    assert "role" in data


def test_refresh_token(client, user_credentials):
    login = client.post("/api/auth/login", json=user_credentials)
    refresh = login.json()["refresh_token"]

    res = client.post("/api/auth/refresh", json={
        "refresh_token": refresh
    })

    assert res.status_code == 200
    assert "access_token" in res.json()


def test_refresh_invalid_token(client):
    res = client.post("/api/auth/refresh", json={
        "refresh_token": "invalid"
    })

    assert res.status_code == 401


def test_logout_invalidates_refresh(client, user_credentials):
    login = client.post("/api/auth/login", json=user_credentials)
    refresh = login.json()["refresh_token"]

    client.post("/api/auth/logout", json={
        "refresh_token": refresh
    })

    res = client.post("/api/auth/refresh", json={
        "refresh_token": refresh
    })

    assert res.status_code == 401