from app.models.schemas import EPcrExtraction


class FakeGroqService:
    def __init__(self) -> None:
        self.transcript = "fake transcript"
        self.epcr = EPcrExtraction()

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        return self.transcript

    async def extract_epcr_data(self, transcript: str) -> EPcrExtraction:
        return self.epcr
