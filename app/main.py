from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.services.groq_service import GroqService
from app.models.schemas import TranscriptionResponse

app = FastAPI(title="ePCR Medical Transcription API", description="Backend for processing EMS audio encounters.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_service = GroqService()

@app.post("/api/v1/process-audio", response_model=TranscriptionResponse)
async def process_audio(file: UploadFile = File(...)):
    """
    Takes an audio file of an EMS encounter, transcribes it using Whisper,
    and extracts organized ePCR fields and a narrative using Llama 3.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
        
    try:
        audio_bytes = await file.read()
        
        # 1. Transcribe the audio via Groq Whisper
        transcript = await groq_service.transcribe_audio(audio_bytes, file.filename)
        
        # 2. Extract structured data and narrative via Groq Llama
        epcr_data = await groq_service.extract_epcr_data(transcript)
        
        return TranscriptionResponse(
            raw_transcript=transcript,
            epcr_data=epcr_data
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}
