def test_user_cannot_access_admin(client, user_token):
    res = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert res.status_code == 403

def test_admin_can_access_admin(client, admin_token):
    res = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200