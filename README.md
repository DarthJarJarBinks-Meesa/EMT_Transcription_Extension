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
   - **`API_KEYS`** (optional) — comma-separated list of additional client secrets so each EMT or device can have its own key. If set, it is **merged** with `API_KEY` (so you can keep one “admin” key and many per-EMT keys). You can use **only** `API_KEYS` if you omit `API_KEY`.

   ```bash
   export GROQ_API_KEY="gsk_..."   # from Groq
   export API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"   # or pick your own secret
   # Optional: per-EMT keys (example — generate real secrets in production)
   # export API_KEYS="$(python -c 'import secrets; print(secrets.token_urlsafe(24)))",$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
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

- Header **`X-API-Key: <one of your configured keys>`**, or  
- Header **`Authorization: Bearer <one of your configured keys>`**

Configured keys are loaded at startup from **`API_KEY`** and/or **`API_KEYS`** (see Configuration). If the header is missing or not in that set, the server responds with **401**.

## Requirements

- Python 3.10 (up to 3.x before 4.0)
- [Poetry](https://python-poetry.org/) (recommended) or pip
- `GROQ_API_KEY` and at least one of `API_KEY` / `API_KEYS` at server startup

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for Whisper and chat models |
| `API_KEY` | Yes† | One client secret; merged with `API_KEYS` if both are set |
| `API_KEYS` | No | Comma- or newline-separated extra client secrets (e.g. one per EMT); merged with `API_KEY` |

† You need at least one key total: `API_KEY` alone, `API_KEYS` alone, or both.
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (empty disables browser cross-origin access) |
| `MAX_UPLOAD_BYTES` | No | Max upload size in bytes (default ~25 MB) |
| `RATE_LIMIT` | No | slowapi limit for `POST /api/v1/process-audio` (default `30/minute`) |
| `ADMIN_API_KEY` | No | If set, enables `GET /admin/usage` with header **`X-Admin-Key`** (separate from client `API_KEY` / `API_KEYS`) |

### Per–API-key usage

While the process is running, the server keeps **in-memory** counters per client key (identified by **`key_fingerprint_sha256`**, i.e. SHA-256 of the raw client secret—same idea as the rate limiter). For each key it tracks:

- **`process_audio_requests`** — authenticated `POST /api/v1/process-audio` calls (including failures after auth).
- **`audio_bytes_transcribed`** — bytes of audio that **finished** speech-to-text successfully.
- **`full_epcr_successes`** — responses that returned **200** with full structured ePCR.

Fetch a snapshot (requires `ADMIN_API_KEY`):

```bash
curl -sS -H "X-Admin-Key: $ADMIN_API_KEY" http://127.0.0.1:8000/admin/usage
```

Counters **reset on restart**; for durable billing or analytics, export this JSON to your own store or add a database later.

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

Add per-EMT keys with another `-e API_KEYS=key1,key2,...` on the same `docker run` command if needed. Then use `curl` or `test_client.py` against `http://127.0.0.1:8000` as above.

## Endpoints

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/api/v1/process-audio` | Multipart field **`file`** (audio). Requires API key header. |
| `GET` | `/admin/usage` | Per-key usage JSON. Requires `ADMIN_API_KEY` and header **`X-Admin-Key`**. |
| `GET` | `/health` | Liveness. |
| `GET` | `/health/ready` | Returns whether the Groq service finished startup. |
