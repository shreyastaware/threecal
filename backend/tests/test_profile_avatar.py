from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.domains.users.avatar import AVATAR_OUTPUT_SIZE, MAX_AVATAR_BYTES
from app.domains.users.storage import get_object_storage


REGISTER_PAYLOAD = {
    "full_name": "Avery Stone",
    "email": "avery@example.com",
    "password": "strong-password",
}


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []
        self.public_base_url = "https://assets.threecal.test"

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        self.objects[key] = (content, content_type)
        return f"{self.public_base_url}/{key}"

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)

    def key_from_public_url(self, public_url: str) -> str | None:
        prefix = f"{self.public_base_url}/"
        return public_url.removeprefix(prefix) if public_url.startswith(prefix) else None


def image_bytes(
    *,
    image_format: str = "PNG",
    size: tuple[int, int] = (900, 600),
) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color=(42, 91, 68)).save(output, format=image_format)
    return output.getvalue()


def authenticated_client(
    client: TestClient,
    storage: FakeObjectStorage,
) -> TestClient:
    client.app.dependency_overrides[get_object_storage] = lambda: storage
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    return client


def test_avatar_is_processed_uploaded_and_saved(client: TestClient) -> None:
    storage = FakeObjectStorage()
    authenticated_client(client, storage)

    response = client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("portrait.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 200
    avatar_url = response.json()["avatar_url"]
    assert avatar_url.startswith(f"{storage.public_base_url}/profile-pictures/")
    key = avatar_url.removeprefix(f"{storage.public_base_url}/")
    stored_content, stored_content_type = storage.objects[key]
    assert stored_content_type == "image/webp"
    with Image.open(BytesIO(stored_content)) as processed:
        assert processed.format == "WEBP"
        assert processed.size == AVATAR_OUTPUT_SIZE

    current_user = client.get("/api/v1/users/me")
    assert current_user.json()["avatar_url"] == avatar_url


def test_replacing_avatar_deletes_previous_managed_object(
    client: TestClient,
) -> None:
    storage = FakeObjectStorage()
    authenticated_client(client, storage)

    first = client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("first.png", image_bytes(), "image/png")},
    )
    first_key = first.json()["avatar_url"].removeprefix(
        f"{storage.public_base_url}/"
    )
    second = client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("second.jpg", image_bytes(image_format="JPEG"), "image/jpeg")},
    )

    assert second.status_code == 200
    assert first_key in storage.deleted
    assert first_key not in storage.objects


def test_avatar_larger_than_five_mb_is_rejected(client: TestClient) -> None:
    storage = FakeObjectStorage()
    authenticated_client(client, storage)

    response = client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("large.jpg", b"x" * (MAX_AVATAR_BYTES + 1), "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "avatar_too_large"
    assert not storage.objects


def test_non_image_avatar_is_rejected(client: TestClient) -> None:
    storage = FakeObjectStorage()
    authenticated_client(client, storage)

    response = client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["code"] == "avatar_type_unsupported"
    assert not storage.objects


def test_corrupt_image_avatar_is_rejected(client: TestClient) -> None:
    storage = FakeObjectStorage()
    authenticated_client(client, storage)

    response = client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("portrait.png", b"not really a png", "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "avatar_invalid"
    assert not storage.objects
