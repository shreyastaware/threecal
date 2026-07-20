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

    event = client.post("/api/v1/event-types", json={"title": "Advisory call", "slug": "advisory", "duration_minutes": 30, "slot_interval_minutes": 30, "price_minor": 50000, "currency": "INR"})
    assert event.status_code == 201

    page = client.get("/api/v1/public/avery/advisory")
    assert page.status_code == 200
    assert page.json()["host"]["bio"] == "Strategy sessions"
    assert "email" not in page.json()["host"]
