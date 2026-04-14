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


def test_process_audio_accepts_any_listed_api_key(monkeypatch):
    """Per-EMT keys via API_KEYS (comma-separated); no API_KEY required."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("API_KEYS", "emt-alpha, emt-beta")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-" + "w" * 40)
    monkeypatch.setenv("RATE_LIMIT", "10000/minute")
    import app.main as main

    with patch.object(main, "create_groq_service", return_value=FakeGroqService()):
        with TestClient(main.app) as tc:
            r = tc.post(
                "/api/v1/process-audio",
                headers={"X-API-Key": "emt-beta"},
                files={"file": ("test.mp3", io.BytesIO(b"\x00\x00" * 200), "audio/mpeg")},
            )
    assert r.status_code == 200


def test_process_audio_merges_api_key_with_api_keys(monkeypatch):
    monkeypatch.setenv("API_KEY", "legacy-admin")
    monkeypatch.setenv("API_KEYS", "emt-one")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-" + "v" * 40)
    monkeypatch.setenv("RATE_LIMIT", "10000/minute")
    import app.main as main

    with patch.object(main, "create_groq_service", return_value=FakeGroqService()):
        with TestClient(main.app) as tc:
            r = tc.post(
                "/api/v1/process-audio",
                headers={"X-API-Key": "legacy-admin"},
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


def test_admin_usage_not_enabled_without_admin_key(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-" + "q" * 40)
    monkeypatch.setenv("RATE_LIMIT", "10000/minute")
    import app.main as main

    with patch.object(main, "create_groq_service", return_value=FakeGroqService()):
        with TestClient(main.app) as tc:
            r = tc.get("/admin/usage", headers={"X-Admin-Key": "anything"})
    assert r.status_code == 404


def test_admin_usage_reports_per_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "admin-secret")
    monkeypatch.setenv("API_KEY", "client-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-" + "p" * 40)
    monkeypatch.setenv("RATE_LIMIT", "10000/minute")
    import app.main as main

    audio = b"\x00\x00" * 200
    with patch.object(main, "create_groq_service", return_value=FakeGroqService()):
        with TestClient(main.app) as tc:
            pr = tc.post(
                "/api/v1/process-audio",
                headers={"X-API-Key": "client-key"},
                files={"file": ("t.mp3", io.BytesIO(audio), "audio/mpeg")},
            )
            assert pr.status_code == 200
            r = tc.get("/admin/usage", headers={"X-Admin-Key": "admin-secret"})
    assert r.status_code == 200
    rows = r.json()["by_key"]
    assert len(rows) == 1
    row = rows[0]
    assert row["process_audio_requests"] == 1
    assert row["audio_bytes_transcribed"] == len(audio)
    assert row["full_epcr_successes"] == 1


def test_usage_transcription_without_full_success(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "adm")
    monkeypatch.setenv("API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-" + "o" * 40)
    monkeypatch.setenv("RATE_LIMIT", "10000/minute")
    import app.main as main

    class BadFake(FakeGroqService):
        async def extract_epcr_data(self, transcript: str) -> EPcrExtraction:
            raise EpcrExtractionError("bad")

    payload = b"x" * 100
    with patch.object(main, "create_groq_service", return_value=BadFake()):
        with TestClient(main.app) as tc:
            pr = tc.post(
                "/api/v1/process-audio",
                headers={"X-API-Key": "k1"},
                files={"file": ("a.mp3", io.BytesIO(payload), "audio/mpeg")},
            )
            assert pr.status_code == 422
            r = tc.get("/admin/usage", headers={"X-Admin-Key": "adm"})
    row = r.json()["by_key"][0]
    assert row["process_audio_requests"] == 1
    assert row["audio_bytes_transcribed"] == len(payload)
    assert row["full_epcr_successes"] == 0
