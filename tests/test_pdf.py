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

def test_delete_foreign_pdf(client, user_token):
    res = client.delete(
        "/api/pdf/999",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert res.status_code in (403, 404)