import asyncio
import io
import json
import logging
import os
from typing import Any

from groq import Groq
from pydantic import ValidationError

from app.exceptions import EpcrExtractionError, GroqServiceError
from app.models.schemas import EPcrExtraction

logger = logging.getLogger(__name__)


class GroqService:
    def __init__(self) -> None:
        if not (os.getenv("GROQ_API_KEY") or "").strip():
            raise GroqServiceError("GROQ_API_KEY is not set.")
        self.client = Groq()
        self.stt_model = "whisper-large-v3"
        self.llm_model = "llama-3.1-8b-instant"

    def _transcribe_sync(self, audio_bytes: bytes, filename: str) -> str:
        """Blocking Groq Whisper call (run in a worker thread)."""
        safe_name = os.path.basename(filename) or "audio.wav"
        buf = io.BytesIO(audio_bytes)
        buf.seek(0)
        try:
            transcription = self.client.audio.transcriptions.create(
                file=(safe_name, buf.read()),
                model=self.stt_model,
                response_format="text",
            )
        except Exception as e:
            logger.error("Groq transcription failed (%s)", type(e).__name__)
            raise GroqServiceError("Speech-to-text request failed.") from e

        if transcription is None:
            return ""
        if isinstance(transcription, str):
            return transcription
        return str(transcription)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Transcribes audio using Groq's Whisper API without blocking the event loop."""
        return await asyncio.to_thread(self._transcribe_sync, audio_bytes, filename)

    def _extract_sync(self, transcript: str) -> EPcrExtraction:
        """Blocking Groq chat completion (run in a worker thread)."""
        schema_json = EPcrExtraction.model_json_schema()
        system_prompt = f"""
        You are an expert EMS documentation assistant.
        Your task is to take a raw spoken transcript of an EMS medical encounter and extract the relevant clinical information into a precise JSON structure.

        You must output ONLY valid JSON that precisely matches the following JSON schema:
        {json.dumps(schema_json)}

        In addition to extracting the fields, you must generate a highly professional 'narrative' field using the standard SOAP or CHART format.
        Do not include any text outside the JSON object.
        """

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Transcript to process:\n\n{transcript}"},
                ],
                model=self.llm_model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
        except Exception as e:
            logger.error("Groq chat completion failed (%s)", type(e).__name__)
            raise GroqServiceError("Structured extraction request failed.") from e

        try:
            message = response.choices[0].message
        except (IndexError, AttributeError) as e:
            raise EpcrExtractionError("Model returned an unexpected response shape.") from e

        content = message.content
        if content is None or not str(content).strip():
            raise EpcrExtractionError("Model returned an empty response.")

        try:
            extracted_data: Any = json.loads(content)
        except json.JSONDecodeError as e:
            raise EpcrExtractionError("Model output was not valid JSON.") from e

        if not isinstance(extracted_data, dict):
            raise EpcrExtractionError("Model JSON was not an object.")

        try:
            return EPcrExtraction.model_validate(extracted_data)
        except ValidationError as e:
            raise EpcrExtractionError("Model JSON did not match the ePCR schema.") from e

    async def extract_epcr_data(self, transcript: str) -> EPcrExtraction:
        """Extracts structured ePCR data and narrative from the transcript."""
        return await asyncio.to_thread(self._extract_sync, transcript)


def create_groq_service() -> GroqService:
    """Factory for lifespan / tests (patch this to inject a fake service)."""
    return GroqService()
