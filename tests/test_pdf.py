def test_upload_pdf(client, user_token):
    with open("test.pdf", "rb") as f:
        res = client.post(
            "/api/pdf/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": ("test.pdf", f, "application/pdf")}
        )

    assert res.status_code == 200

def test_upload_non_pdf(client, user_token):
    with open("test.txt", "rb") as f:
        res = client.post(
            "/api/pdf/upload",
            headers={"Authorization": f"Bearer {user_token}"},
            files={"file": ("test.txt", f, "text/plain")}
        )

    assert res.status_code == 400

def test_delete_foreign_pdf(client, user_token):
    res = client.delete(
        "/api/pdf/999",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert res.status_code in (403, 404)