import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.exceptions import EpcrExtractionError, GroqServiceError
from app.models.schemas import EPcrExtraction
from tests.fakes import FakeGroqService


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readiness(client: TestClient):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True


def test_process_audio_unauthorized(client: TestClient):
    r = client.post(
        "/api/v1/process-audio",
        files={"file": ("test.mp3", io.BytesIO(b"\x00\x00"), "audio/mpeg")},
    )
    assert r.status_code == 401


def test_process_audio_bearer_auth(monkeypatch):
    monkeypatch.setenv("API_KEY", "bearer-secret")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-" + "z" * 40)
    monkeypatch.setenv("RATE_LIMIT", "10000/minute")
    import app.main as main

    with patch.object(main, "create_groq_service", return_value=FakeGroqService()):
        with TestClient(main.app) as tc:
            r = tc.post(
                "/api/v1/process-audio",
                headers={"Authorization": "Bearer bearer-secret"},
                files={"file": ("test.mp3", io.BytesIO(b"\x00\x00" * 200), "audio/mpeg")},
            )
    assert r.status_code == 200


def test_process_audio_success(client: TestClient, auth_headers: dict[str, str]):
    r = client.post(
        "/api/v1/process-audio",
        headers=auth_headers,
        files={"file": ("test.mp3", io.BytesIO(b"\x00\x00" * 200), "audio/mpeg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["raw_transcript"] == "fake transcript"
    assert "epcr_data" in body


def test_process_audio_bad_extension(client: TestClient, auth_headers: dict[str, str]):
    r = client.post(
        "/api/v1/process-audio",
        headers=auth_headers,
        files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")},
    )
    assert r.status_code == 415


def test_process_audio_extraction_error(client: TestClient, auth_headers: dict[str, str]):
    class BadFake(FakeGroqService):
        async def extract_epcr_data(self, transcript: str) -> EPcrExtraction:
            raise EpcrExtractionError("bad")

    import app.main as main

    with patch.object(main, "create_groq_service", return_value=BadFake()):
        with TestClient(main.app) as tc:
            r = tc.post(
                "/api/v1/process-audio",
                headers=auth_headers,
                files={"file": ("a.mp3", io.BytesIO(b"x" * 100), "audio/mpeg")},
            )
    assert r.status_code == 422


def test_process_audio_groq_error(client: TestClient, auth_headers: dict[str, str]):
    class FailFake(FakeGroqService):
        async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
            raise GroqServiceError("x")

    import app.main as main

    with patch.object(main, "create_groq_service", return_value=FailFake()):
        with TestClient(main.app) as tc:
            r = tc.post(
                "/api/v1/process-audio",
                headers=auth_headers,
                files={"file": ("a.mp3", io.BytesIO(b"x" * 100), "audio/mpeg")},
            )
    assert r.status_code == 502
