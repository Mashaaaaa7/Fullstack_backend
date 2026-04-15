def test_upload_pdf(client, user_token):
    file_content = b"%PDF-1.4 dummy content"
    response = client.post(
        "/api/pdf/upload",
        files={"file": ("test.pdf", file_content, "application/pdf")},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 200

def test_upload_non_pdf(client, user_token):
    file_content = b"hello world"
    response = client.post(
        "/api/pdf/upload",
        files={"file": ("test.txt", file_content, "text/plain")},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 400

def test_delete_own_pdf(client, user_token):
    file_content = b"%PDF-1.4 dummy content"
    upload = client.post(
        "/api/pdf/upload",
        files={"file": ("test.pdf", file_content, "application/pdf")},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert upload.status_code == 200
    pdf_id = upload.json()["file_id"]

    res = client.delete(
        f"/api/pdf/{pdf_id}",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert res.status_code in (200, 204)

def test_delete_foreign_pdf(client, user_token):
    res = client.delete(
        "/api/pdf/999",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert res.status_code in (403, 404)

def test_admin_cannot_see_other_users_pdfs(client, user_token, admin_token):
    # Пользователь загружает файл
    file_content = b"%PDF-1.4 dummy content"
    upload = client.post(
        "/api/pdf/upload",
        files={"file": ("user_private.pdf", file_content, "application/pdf")},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert upload.status_code == 200

    # Администратор запрашивает список — не должен видеть файл пользователя
    res = client.get(
        "/api/pdf/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    pdf_names = [p["filename"] for p in res.json()]
    assert "user_private.pdf" not in pdf_names