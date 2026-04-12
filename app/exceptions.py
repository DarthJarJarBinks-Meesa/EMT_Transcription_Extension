"""Domain errors raised by services (mapped to HTTP in routes)."""


class EpcrExtractionError(Exception):
    """LLM output could not be parsed or did not match the ePCR schema."""

    def __init__(self, message: str = "Model output was not valid structured data."):
        super().__init__(message)


class GroqServiceError(Exception):
    """Groq API or client failure (network, auth, quota, etc.)."""

    def __init__(self, message: str = "Upstream speech or language service failed."):
        super().__init__(message)
