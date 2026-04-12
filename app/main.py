import hashlib
import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import Response

from app.exceptions import EpcrExtractionError, GroqServiceError
from app.models.schemas import TranscriptionResponse
from app.services.groq_service import GroqService, create_groq_service

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))

_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else []
)

RATE_LIMIT: str = os.getenv("RATE_LIMIT", "30/minute")

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


def _rate_limit_key(request: Request) -> str:
    """Prefer hashed API key for per-client limits; fall back to client IP."""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip().encode()
        if token:
            return hashlib.sha256(token).hexdigest()
    xk = request.headers.get("x-api-key")
    if xk:
        return hashlib.sha256(xk.strip().encode()).hexdigest()
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """Adapter so FastAPI's exception handler typing accepts `Exception`."""
    if not isinstance(exc, RateLimitExceeded):
        raise exc
    return _rate_limit_exceeded_handler(request, exc)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = (os.getenv("API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "API_KEY must be set to a non-empty value before starting the server."
        )
    if not (os.getenv("GROQ_API_KEY") or "").strip():
        raise RuntimeError(
            "GROQ_API_KEY must be set to a non-empty value before starting the server."
        )

    app.state.groq_service = create_groq_service()
    logger.info("GroqService initialised (async entrypoints offload blocking Groq calls)")
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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> bool:
    expected = (os.getenv("API_KEY") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Server is not configured with API_KEY.",
        )

    token: str | None = None
    if authorization:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
    if token is None and x_api_key:
        token = x_api_key.strip()

    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return True


def get_groq_service(request: Request) -> GroqService:
    return request.app.state.groq_service


@app.post("/api/v1/process-audio", response_model=TranscriptionResponse)
@limiter.limit(RATE_LIMIT)
async def process_audio(
    request: Request,
    file: Annotated[UploadFile, File()],
    groq_service: Annotated[GroqService, Depends(get_groq_service)],
    _authorized: Annotated[bool, Depends(verify_api_key)],
):
    """
    Takes an audio file of an EMS encounter, transcribes it using Whisper,
    and extracts organised ePCR fields and a SOAP narrative using Llama 3.
    """
    raw_name: str = (file.filename or "").strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Please upload an audio file.",
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported media type. Please upload an audio file.",
        )

    audio_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    try:
        transcript = await groq_service.transcribe_audio(audio_bytes, raw_name)
        epcr_data = await groq_service.extract_epcr_data(transcript)
        return TranscriptionResponse(raw_transcript=transcript, epcr_data=epcr_data)

    except HTTPException:
        raise
    except EpcrExtractionError as e:
        logger.warning("ePCR extraction failed: %s", type(e).__name__)
        raise HTTPException(
            status_code=422,
            detail="Could not produce valid structured documentation from the transcript.",
        ) from e
    except GroqServiceError:
        logger.error("Groq service error in process_audio (upstream failure)")
        raise HTTPException(
            status_code=502,
            detail="The upstream AI service failed. Please try again later.",
        ) from None
    except Exception:
        logger.exception("Unhandled error in process_audio")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from None


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "emt-epcr-backend"}


@app.get("/health/ready")
def readiness(request: Request):
    """Returns whether core app dependencies were initialised (after lifespan)."""
    ok = getattr(request.app.state, "groq_service", None) is not None
    return {"ready": ok}
