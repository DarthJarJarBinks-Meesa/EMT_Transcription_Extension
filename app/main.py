import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import TranscriptionResponse
from app.services.groq_service import GroqService

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# Maximum accepted upload size (25 MB).  Tune via env var if needed.
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))

# Allowed CORS origins.  Override with a comma-separated list in production:
#   ALLOWED_ORIGINS="https://app.example.com,https://admin.example.com"
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else []          # empty list → no cross-origin requests permitted
)

# Permitted audio MIME types and file extensions.
ALLOWED_AUDIO_MIME_TYPES: frozenset[str] = frozenset(
    {
        "audio/mpeg",
        "audio/mp4",
        "audio/wav",
        "audio/x-wav",
        "audio/webm",
        "audio/ogg",
        "audio/flac",
        "audio/aac",
        "audio/x-m4a",
    }
)
ALLOWED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".mp4", ".wav", ".webm", ".ogg", ".flac", ".aac", ".m4a", ".mpeg"}
)


# ---------------------------------------------------------------------------
# Lifespan — initialise / tear-down shared resources once per process
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.groq_service = GroqService()
    logger.info("GroqService initialised")
    yield
    logger.info("Shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ePCR Medical Transcription API",
    description="Backend for processing EMS audio encounters.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------
def get_groq_service(request: Request) -> GroqService:
    return request.app.state.groq_service


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/api/v1/process-audio", response_model=TranscriptionResponse)
async def process_audio(
    file: UploadFile = File(...),
    groq_service: Annotated[GroqService, Depends(get_groq_service)] = ...,  # type: ignore[assignment]
):
    """
    Takes an audio file of an EMS encounter, transcribes it using Whisper,
    and extracts organised ePCR fields and a SOAP narrative using Llama 3.
    """
    # --- filename validation ---
    raw_name: str = (file.filename or "").strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Please upload an audio file.",
        )

    # --- MIME type validation (when the client sends a content-type) ---
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported media type. Please upload an audio file.",
        )

    # --- file size guard (read in one shot, reject if over limit) ---
    audio_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    try:
        # 1. Transcribe the audio via Groq Whisper
        transcript = await groq_service.transcribe_audio(audio_bytes, raw_name)

        # 2. Extract structured data and narrative via Groq Llama
        epcr_data = await groq_service.extract_epcr_data(transcript)

        return TranscriptionResponse(
            raw_transcript=transcript,
            epcr_data=epcr_data,
        )

    except HTTPException:
        raise
    except Exception:
        # Log the full traceback server-side; never send internals to the client.
        logger.exception("Unhandled error in process_audio")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        )


@app.get("/health")
def health_check():
    return {"status": "healthy"}
