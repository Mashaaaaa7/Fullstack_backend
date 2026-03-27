import io

def test_upload_pdf(client):
    file_content = b"%PDF-1.4 dummy content"
    file_name = 'test.pdf'

    response = client.post(
        "/upload-pdf",
        files={"file": (file_name, file_content, "application/pdf")}
    )

    assert response.status_code == 404


def test_upload_non_pdf(client):
    file_content =  b"hello world"
    file_name = 'test.txt'

    response = client.post(
        "/upload-pdf",
        files={"file": (file_name, file_content, "application/pdf")}
    )

    assert response.status_code == 404

def test_delete_foreign_pdf(client, user_token):
    res = client.delete(
        "/api/pdf/999",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert res.status_code in (403, 404)