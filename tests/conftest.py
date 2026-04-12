from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeGroqService


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-" + "x" * 40)
    monkeypatch.setenv("RATE_LIMIT", "10000/minute")

    import app.main as main

    with patch.object(main, "create_groq_service", return_value=FakeGroqService()):
        with TestClient(main.app) as tc:
            yield tc


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": "test-api-key"}
