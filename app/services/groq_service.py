import os
import json
from groq import Groq
from app.models.schemas import EPcrExtraction

class GroqService:
    def __init__(self):
        # API key inferred from GROQ_API_KEY env var
        self.client = Groq()
        self.stt_model = "whisper-large-v3"
        self.llm_model = "llama-3.1-8b-instant"

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """
        Transcribes audio using Groq's Whisper API.
        """
        temp_file_path = f"/tmp/{os.path.basename(filename)}"
        with open(temp_file_path, "wb") as f:
            f.write(audio_bytes)
            
        try:
            with open(temp_file_path, "rb") as file_obj:
                transcription = self.client.audio.transcriptions.create(
                    file=(filename, file_obj.read()),
                    model=self.stt_model,
                    response_format="text"
                )
            return transcription
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    async def extract_epcr_data(self, transcript: str) -> EPcrExtraction:
        """
        Extracts structured ePCR data and narrative from the transcript using Groq LLM.
        """
        schema_json = EPcrExtraction.model_json_schema()
        
        system_prompt = f"""
        You are an expert EMS documentation assistant. 
        Your task is to take a raw spoken transcript of an EMS medical encounter and extract the relevant clinical information into a precise JSON structure.
        
        You must output ONLY valid JSON that precisely matches the following JSON schema:
        {json.dumps(schema_json)}
        
        In addition to extracting the fields, you must generate a highly professional 'narrative' field using the standard SOAP or CHART format. 
        Do not include any text outside the JSON object.
        """
        
        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Transcript to process:\n\n{transcript}"}
            ],
            model=self.llm_model,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        content = response.choices[0].message.content
        extracted_data = json.loads(content)
        
        return EPcrExtraction(**extracted_data)
