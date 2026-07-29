from fastapi.testclient import TestClient


REGISTER_PAYLOAD = {
    "full_name": "Avery Stone",
    "email": "avery@example.com",
    "password": "strong-password",
}

ACCOUNT_PAYLOAD = {
    "account_name": "Avery Stone",
    "account_email": "accounts@example.com",
    "business_type": "private_limited",
    "business_name": "Stone Health Private Limited",
    "branch_ifsc_code": "HDFC0001234",
    "account_number": "123456789012",
    "beneficiary_name": "Stone Health Private Limited",
}


def test_payment_account_create_read_and_update_are_masked(
    client: TestClient,
) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    empty = client.get("/api/v1/payments/account")
    created = client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)
    fetched = client.get("/api/v1/payments/account")
    updated = client.patch(
        "/api/v1/payments/account",
        json={
            **ACCOUNT_PAYLOAD,
            "account_name": "Avery Finance",
            "branch_ifsc_code": "icic0005678",
            "account_number": None,
        },
    )

    assert empty.status_code == 200
    assert empty.json() is None
    assert created.status_code == 201
    assert created.json()["masked_account_number"] == "123*********"
    assert "account_number" not in created.json()
    assert fetched.json() == created.json()
    assert updated.status_code == 200
    assert updated.json()["account_name"] == "Avery Finance"
    assert updated.json()["branch_ifsc_code"] == "ICIC0005678"
    assert updated.json()["masked_account_number"] == "123*********"


def test_payment_account_can_replace_the_saved_account_number(
    client: TestClient,
) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)

    response = client.patch(
        "/api/v1/payments/account",
        json={
            **ACCOUNT_PAYLOAD,
            "account_number": "987654321",
        },
    )

    assert response.status_code == 200
    assert response.json()["masked_account_number"] == "987******"


def test_payment_account_rejects_duplicate_and_invalid_details(
    client: TestClient,
) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    first = client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)
    duplicate = client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)
    invalid = client.patch(
        "/api/v1/payments/account",
        json={
            **ACCOUNT_PAYLOAD,
            "branch_ifsc_code": "invalid",
            "account_number": None,
        },
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "payment_account_already_exists"
    assert invalid.status_code == 422
