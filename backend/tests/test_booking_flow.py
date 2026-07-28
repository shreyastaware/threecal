from datetime import date, timedelta

from fastapi.testclient import TestClient


def test_profile_schedule_and_public_booking_page(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json={"full_name": "Avery Stone", "email": "avery@example.com", "password": "strong-password"})
    profile = client.patch("/api/v1/users/me", json={"username": "avery", "bio": "Strategy sessions", "timezone": "UTC"})
    assert profile.status_code == 200

    weekday = (date.today() + timedelta(days=1)).weekday()
    schedule = client.put("/api/v1/availability", json={"working_hours": [{"weekday": weekday, "start_time": "09:00", "end_time": "17:00", "is_enabled": True, "breaks": [{"start_time": "12:00", "end_time": "13:00"}]}]})
    assert schedule.status_code == 200
    assert schedule.json()[0]["breaks"]

    event = client.post("/api/v1/event-types", json={"title": "Advisory call", "duration_minutes": 30, "slot_interval_minutes": 30, "price_minor": 50000, "currency": "INR"})
    assert event.status_code == 201
    assert event.json()["slug"] == "30min-2"

    public_profile = client.get("/api/v1/public/avery")
    assert public_profile.status_code == 200
    assert public_profile.json()["host"]["full_name"] == "Avery Stone"
    assert public_profile.json()["default_event_type_slug"] is None
    assert "30min-2" in {
        item["slug"] for item in public_profile.json()["event_types"]
    }

    page = client.get("/api/v1/public/avery/30min-2")
    assert page.status_code == 200
    assert page.json()["host"]["bio"] == "Strategy sessions"
    assert "email" not in page.json()["host"]


def test_event_type_slugs_are_generated_from_duration(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Avery Stone",
            "email": "avery@example.com",
            "password": "strong-password",
        },
    )
    first = client.post(
        "/api/v1/event-types",
        json={
            "title": "First consultation",
            "duration_minutes": 45,
            "slot_interval_minutes": 30,
        },
    )
    second = client.post(
        "/api/v1/event-types",
        json={
            "title": "Second consultation",
            "duration_minutes": 45,
            "slot_interval_minutes": 30,
        },
    )

    assert first.status_code == 201
    assert first.json()["slug"] == "45min"
    assert first.json()["currency"] == "INR"
    assert second.status_code == 201
    assert second.json()["slug"] == "45min-2"

    second_payload = {
        key: value
        for key, value in second.json().items()
        if key not in {"id", "slug"}
    }
    second_payload["duration_minutes"] = 75
    updated = client.patch(
        f"/api/v1/event-types/{second.json()['id']}",
        json=second_payload,
    )
    assert updated.status_code == 200
    assert updated.json()["slug"] == "75min"


def test_event_type_can_be_deleted(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Avery Stone",
            "email": "avery@example.com",
            "password": "strong-password",
        },
    )
    client.patch(
        "/api/v1/users/me",
        json={"username": "avery", "timezone": "UTC"},
    )
    event = client.get("/api/v1/event-types").json()[0]

    deleted = client.delete(f"/api/v1/event-types/{event['id']}")

    assert deleted.status_code == 204
    assert event["id"] not in {
        item["id"] for item in client.get("/api/v1/event-types").json()
    }
    assert client.get(f"/api/v1/public/avery/{event['slug']}").status_code == 404

    deleted_again = client.delete(f"/api/v1/event-types/{event['id']}")
    assert deleted_again.status_code == 404
    assert deleted_again.json()["code"] == "event_type_not_found"


def test_default_event_type_is_unique_and_public(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Avery Stone",
            "email": "avery@example.com",
            "password": "strong-password",
        },
    )
    client.patch(
        "/api/v1/users/me",
        json={"username": "avery", "timezone": "UTC"},
    )
    event_types = client.get("/api/v1/event-types").json()
    thirty_minute = next(
        event for event in event_types if event["slug"] == "30min"
    )
    sixty_minute = next(
        event for event in event_types if event["slug"] == "60min"
    )

    set_thirty_default = client.patch(
        f"/api/v1/event-types/{thirty_minute['id']}",
        json={
            **{key: value for key, value in thirty_minute.items() if key != "id"},
            "is_default": True,
        },
    )
    assert set_thirty_default.status_code == 200
    assert set_thirty_default.json()["is_default"] is True
    assert (
        client.get("/api/v1/public/avery").json()["default_event_type_slug"]
        == "30min"
    )

    set_sixty_default = client.patch(
        f"/api/v1/event-types/{sixty_minute['id']}",
        json={
            **{key: value for key, value in sixty_minute.items() if key != "id"},
            "is_default": True,
        },
    )
    assert set_sixty_default.status_code == 200
    defaults = [
        event
        for event in client.get("/api/v1/event-types").json()
        if event["is_default"]
    ]
    assert [event["slug"] for event in defaults] == ["60min"]
    assert (
        client.get("/api/v1/public/avery").json()["default_event_type_slug"]
        == "60min"
    )

    hidden_default = client.patch(
        f"/api/v1/event-types/{sixty_minute['id']}",
        json={
            **{key: value for key, value in sixty_minute.items() if key != "id"},
            "is_active": False,
            "is_default": True,
        },
    )
    assert hidden_default.status_code == 422
    assert hidden_default.json()["code"] == "default_event_type_inactive"
