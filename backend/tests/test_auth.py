from fastapi.testclient import TestClient


REGISTER_PAYLOAD = {
    "full_name": "Avery Stone",
    "email": "avery@example.com",
    "password": "strong-password",
}


def test_register_sets_cookie_and_authenticates_user(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "avery@example.com"
    assert response.cookies.get("threecal_access_token")
    assert "HttpOnly" in response.headers["set-cookie"]

    me_response = client.get("/api/v1/users/me")
    assert me_response.status_code == 200
    assert me_response.json()["full_name"] == "Avery Stone"

    event_types = client.get("/api/v1/event-types")
    assert event_types.status_code == 200
    assert {
        (event["title"], event["duration_minutes"], event["is_default"])
        for event in event_types.json()
    } == {
        ("30-minute call", 30, False),
        ("60-minute call", 60, False),
    }


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_login_and_logout_cookie_flow(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    client.post("/api/v1/auth/logout")

    unauthenticated = client.get("/api/v1/users/me")
    assert unauthenticated.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "AVERY@example.com", "password": "strong-password"},
    )
    assert login.status_code == 200

    authenticated = client.get("/api/v1/users/me")
    assert authenticated.status_code == 200


def test_invalid_login_does_not_reveal_account_state(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "incorrect"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Email or password is incorrect.",
        "code": "invalid_credentials",
    }
