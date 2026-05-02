# ePCR frontend (local dev)

Serve this folder over **HTTP** so the browser can call your API (`fetch` + CORS). Opening `index.html` as `file://` usually fails.

## 1. Start the API with CORS

From the repo root (`emt_epcr_backend/`):

```bash
export ALLOWED_ORIGINS="http://127.0.0.1:5500,http://localhost:5500"
export GROQ_API_KEY="..."
export API_KEY="..."
poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Change the comma-separated origins if you use another port.

## 2. Serve this directory

From `docs/`:

```bash
python -m http.server 5500
```

Open **http://127.0.0.1:5500**

## 3. In the UI

- **API Base URL:** `http://127.0.0.1:8000`
- **Client API Key:** same value as server `API_KEY`

Then drag an audio file and click **Process Audio**.
