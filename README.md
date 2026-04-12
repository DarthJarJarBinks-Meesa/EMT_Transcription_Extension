# ePCR Medical Transcription API

FastAPI backend that accepts EMS encounter audio, transcribes it with Groq Whisper, and extracts structured ePCR fields plus narratives with Groq Llama.

## Requirements

- Python 3.10+
- [Poetry](https://python-poetry.org/) (recommended) or pip
- `GROQ_API_KEY` and `API_KEY` (both required at process startup)

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for Whisper and chat models |
| `API_KEY` | Yes | Shared secret clients send as `X-API-Key` or `Authorization: Bearer …` |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (empty disables browser cross-origin access) |
| `MAX_UPLOAD_BYTES` | No | Max upload size in bytes (default ~25 MB) |
| `RATE_LIMIT` | No | slowapi limit for `POST /api/v1/process-audio` (default `30/minute`) |

Do not log raw transcripts or responses in production; treat audio and JSON as PHI under your compliance program.

## Run locally

```bash
cd emt_epcr_backend
poetry install --extras dev --no-root
export GROQ_API_KEY=...
export API_KEY=...
poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Tests

```bash
poetry install --extras dev --no-root
poetry run pytest
```

## Manual HTTP check

With the server running:

```bash
export API_KEY=...   # same as server
python test_client.py /path/to/audio.mp3
```

## Docker

```bash
docker build -t emt-epcr-backend .
docker run --rm -p 8000:8000 \
  -e GROQ_API_KEY=... \
  -e API_KEY=... \
  emt-epcr-backend
```

## Endpoints

- `POST /api/v1/process-audio` — multipart file field `file`; requires API key header
- `GET /health` — liveness
- `GET /health/ready` — Groq service initialised after startup
