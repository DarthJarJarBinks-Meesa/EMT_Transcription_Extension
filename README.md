# ePCR Medical Transcription API

FastAPI backend that accepts EMS encounter audio, transcribes it with Groq Whisper, and extracts structured ePCR fields plus narratives with Groq Llama.

## Quick start

1. **Install dependencies**

   ```bash
   cd emt_epcr_backend
   poetry install --extras dev --no-root
   ```

2. **Set two different secrets** (both required for the server to start):

   - **`GROQ_API_KEY`** — from your [Groq console](https://console.groq.com/). Used only on the server to call Groq.
   - **`API_KEY`** — any long random string **you invent**. Clients must send this to call your API; it is **not** your Groq key.

   ```bash
   export GROQ_API_KEY="gsk_..."   # from Groq
   export API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"   # or pick your own secret
   ```

3. **Start the API** (leave this terminal running):

   ```bash
   poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. **Try it from a second terminal** (same machine):

   ```bash
   cd emt_epcr_backend
   export API_KEY="paste-the-same-value-as-on-the-server"
   ```

   Check health:

   ```bash
   curl -sS http://127.0.0.1:8000/health
   ```

   Send the bundled example clip (hyperglycemia scenario — synthetic / demo audio, not real PHI):

   ```bash
   curl -sS -X POST "http://127.0.0.1:8000/api/v1/process-audio" \
     -H "X-API-Key: $API_KEY" \
     -F "file=@audio_hyperglycemia.mp3;type=audio/mpeg"
   ```

   Or use the helper script (also needs `API_KEY` in the environment):

   ```bash
   python test_client.py audio_hyperglycemia.mp3
   ```

5. **Explore the API in a browser** (while the server is running):

   - [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) — Swagger UI (`POST /api/v1/process-audio`: click “Try it out”, add header `X-API-Key`, upload a file).
   - [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) — liveness.

   The site root [http://127.0.0.1:8000/](http://127.0.0.1:8000/) has no route defined, so you will see `{"detail":"Not Found"}` — that is expected.

## Example audio

This repo includes **`audio_hyperglycemia.mp3`** at the project root so you can try the pipeline without recording your own file. Other `*.mp3` files remain gitignored by default.

## Authentication

Every `POST /api/v1/process-audio` request must include **one** of:

- Header **`X-API-Key: <your API_KEY>`**, or  
- Header **`Authorization: Bearer <your API_KEY>`**

If the header is missing or wrong, the server responds with **401**.

## Requirements

- Python 3.10 (up to 3.x before 4.0)
- [Poetry](https://python-poetry.org/) (recommended) or pip
- `GROQ_API_KEY` and `API_KEY` at server startup

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for Whisper and chat models |
| `API_KEY` | Yes | Shared secret clients send as `X-API-Key` or `Authorization: Bearer …` |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (empty disables browser cross-origin access) |
| `MAX_UPLOAD_BYTES` | No | Max upload size in bytes (default ~25 MB) |
| `RATE_LIMIT` | No | slowapi limit for `POST /api/v1/process-audio` (default `30/minute`) |

Do not log raw transcripts or responses in production; treat audio and JSON as PHI under your compliance program.

## Tests

```bash
poetry install --extras dev --no-root
poetry run pytest
```

## Docker

```bash
docker build -t emt-epcr-backend .
docker run --rm -p 8000:8000 \
  -e GROQ_API_KEY=... \
  -e API_KEY=... \
  emt-epcr-backend
```

Then use `curl` or `test_client.py` against `http://127.0.0.1:8000` as above.

## Endpoints

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/api/v1/process-audio` | Multipart field **`file`** (audio). Requires API key header. |
| `GET` | `/health` | Liveness. |
| `GET` | `/health/ready` | Returns whether the Groq service finished startup. |
