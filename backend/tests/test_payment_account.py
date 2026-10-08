from fastapi.testclient import TestClient

from tests.razorpay_fakes import (
    ACCOUNT_ID,
    ACCOUNT_PAYLOAD,
    PRODUCT_ID,
    STAKEHOLDER_ID,
    FakeRazorpay,
    razorpay,  # noqa: F401
)


REGISTER_PAYLOAD = {
    "full_name": "Avery Stone",
    "email": "avery@example.com",
    "password": "strong-password",
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
            "pan": None,
        },
    )

    assert empty.status_code == 200
    assert empty.json() is None
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["masked_account_number"] == "123*********"
    assert body["masked_pan"] == "AA*******C"
    assert body["phone"] == "919876543210"
    assert body["street2"] is None
    assert "account_number" not in body
    assert "pan" not in body
    # Without platform Razorpay keys the details are saved but payouts stay off.
    assert body["activation_status"] == "not_started"
    assert body["payouts_enabled"] is False
    assert body["payouts_configured"] is False
    assert fetched.json() == created.json()
    assert updated.status_code == 200
    assert updated.json()["account_name"] == "Avery Finance"
    assert updated.json()["branch_ifsc_code"] == "ICIC0005678"
    assert updated.json()["masked_account_number"] == "123*********"
    assert updated.json()["masked_pan"] == "AA*******C"


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
    wrong_subcategory = client.patch(
        "/api/v1/payments/account",
        json={**ACCOUNT_PAYLOAD, "business_subcategory": "saas"},
    )
    personal_pan_for_company = client.patch(
        "/api/v1/payments/account",
        json={**ACCOUNT_PAYLOAD, "pan": "ABCPE1234F"},
    )
    business_pan_for_individual = client.patch(
        "/api/v1/payments/account",
        json={**ACCOUNT_PAYLOAD, "business_type": "individual"},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "payment_account_already_exists"
    assert invalid.status_code == 422
    assert wrong_subcategory.status_code == 422
    assert personal_pan_for_company.status_code == 422
    assert business_pan_for_individual.status_code == 422


def test_creating_account_onboards_route_linked_account(
    client: TestClient,
    razorpay: FakeRazorpay,  # noqa: F811
) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    created = client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)

    assert created.status_code == 201, created.text
    assert created.json()["activation_status"] == "activated"
    assert created.json()["payouts_enabled"] is True
    assert created.json()["payouts_configured"] is True
    assert razorpay.paths() == [
        "/v2/accounts",
        f"/v2/accounts/{ACCOUNT_ID}/stakeholders",
        f"/v2/accounts/{ACCOUNT_ID}/products",
        f"/v2/accounts/{ACCOUNT_ID}/products/{PRODUCT_ID}/",
    ]
    account = razorpay.body("POST", "/v2/accounts")
    assert account["type"] == "route"
    assert account["email"] == "accounts@example.com"
    assert account["phone"] == "919876543210"
    assert account["business_type"] == "private_limited"
    assert account["legal_business_name"] == "Stone Health Private Limited"
    assert account["profile"]["category"] == "healthcare"
    assert account["profile"]["subcategory"] == "clinic"
    assert account["profile"]["addresses"]["registered"] == {
        "street1": "507, Koramangala 1st block",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560034",
        "country": "IN",
    }
    # A company sends its business PAN on the account, not the stakeholder.
    assert account["legal_info"] == {"pan": "AAACS1234C"}
    assert "kyc" not in razorpay.body("POST", f"/v2/accounts/{ACCOUNT_ID}/stakeholders")
    assert razorpay.body("POST", f"/v2/accounts/{ACCOUNT_ID}/products") == {"product_name": "route", "tnc_accepted": True}
    assert razorpay.body("PATCH", f"/v2/accounts/{ACCOUNT_ID}/products/{PRODUCT_ID}/") == {
        "settlements": {
            "account_number": "123456789012",
            "ifsc_code": "HDFC0001234",
            "beneficiary_name": "Stone Health Private Limited",
        },
        "tnc_accepted": True,
    }


def test_individual_pan_goes_on_the_stakeholder(
    client: TestClient,
    razorpay: FakeRazorpay,  # noqa: F811
) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    created = client.post(
        "/api/v1/payments/account",
        json={**ACCOUNT_PAYLOAD, "business_type": "individual", "pan": "abcpe1234f"},
    )

    assert created.status_code == 201, created.text
    assert "legal_info" not in razorpay.body("POST", "/v2/accounts")
    assert razorpay.body("POST", f"/v2/accounts/{ACCOUNT_ID}/stakeholders")["kyc"] == {"pan": "ABCPE1234F"}


def test_pending_requirements_are_shown_and_sync_refreshes_status(
    client: TestClient,
    razorpay: FakeRazorpay,  # noqa: F811
) -> None:
    razorpay.activation_status = "needs_clarification"
    razorpay.requirements = [
        {
            "field_reference": "settlements.beneficiary_name",
            "reason_code": "needs_clarification",
            "status": "required",
            "description": "Beneficiary name does not match the bank records.",
        }
    ]
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    created = client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)
    razorpay.activation_status = "activated"
    razorpay.requirements = []
    synced = client.post("/api/v1/payments/account/sync")

    assert created.json()["activation_status"] == "needs_clarification"
    assert created.json()["payouts_enabled"] is False
    assert created.json()["requirements"][0]["field_reference"] == "settlements.beneficiary_name"
    assert synced.status_code == 200
    assert synced.json()["activation_status"] == "activated"
    assert synced.json()["requirements"] == []
    assert razorpay.paths("GET") == [f"/v2/accounts/{ACCOUNT_ID}/products/{PRODUCT_ID}/"]


def test_provider_failure_is_reported_and_onboarding_resumes(
    client: TestClient,
    razorpay: FakeRazorpay,  # noqa: F811
) -> None:
    razorpay.failures[("POST", f"/v2/accounts/{ACCOUNT_ID}/stakeholders")] = (400, "Invalid stakeholder email")
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    failed = client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)
    saved = client.get("/api/v1/payments/account")
    retried = client.patch("/api/v1/payments/account", json={**ACCOUNT_PAYLOAD, "account_number": None, "pan": None})

    assert failed.status_code == 422
    assert failed.json()["code"] == "payment_provider_rejected"
    assert "Invalid stakeholder email" in failed.json()["detail"]
    assert saved.json()["activation_status"] == "not_started"
    assert retried.status_code == 200, retried.text
    assert retried.json()["activation_status"] == "activated"
    # The linked account created before the failure is reused.
    assert razorpay.paths("POST").count("/v2/accounts") == 1


def test_locked_fields_and_updates_after_onboarding(
    client: TestClient,
    razorpay: FakeRazorpay,  # noqa: F811
) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    client.post("/api/v1/payments/account", json=ACCOUNT_PAYLOAD)

    locked = client.patch(
        "/api/v1/payments/account",
        json={**ACCOUNT_PAYLOAD, "account_email": "new@example.com", "pan": None},
    )
    updated = client.patch(
        "/api/v1/payments/account",
        json={**ACCOUNT_PAYLOAD, "account_number": "555566667777", "pan": None},
    )

    assert locked.status_code == 409
    assert locked.json()["code"] == "payment_account_locked_fields"
    assert updated.status_code == 200
    assert f"/v2/accounts/{ACCOUNT_ID}" in razorpay.paths("PATCH")
    assert f"/v2/accounts/{ACCOUNT_ID}/stakeholders/{STAKEHOLDER_ID}" in razorpay.paths("PATCH")
    assert "email" not in razorpay.body("PATCH", f"/v2/accounts/{ACCOUNT_ID}")
    assert razorpay.body("PATCH", f"/v2/accounts/{ACCOUNT_ID}/products/{PRODUCT_ID}/")["settlements"]["account_number"] == "555566667777"
