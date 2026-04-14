from typing import List, Optional

from pydantic import BaseModel, Field


class PatientDemographics(BaseModel):
    name: Optional[str] = Field(default=None, description="Patient's full name if provided")
    age: Optional[str] = Field(default=None, description="Patient's age")
    gender: Optional[str] = Field(default=None, description="Patient's gender")


class VitalSigns(BaseModel):
    heart_rate: Optional[str] = Field(default=None, description="Heart rate / pulse")
    blood_pressure: Optional[str] = Field(default=None, description="Blood pressure")
    respiratory_rate: Optional[str] = Field(default=None, description="Respiratory rate")
    spo2: Optional[str] = Field(default=None, description="Oxygen saturation (SpO2)")
    gcs: Optional[str] = Field(default=None, description="Glasgow Coma Scale")


class AssessmentInfo(BaseModel):
    chief_complaint: Optional[str] = Field(default=None, description="The primary reason for the ambulance call")
    symptoms: Optional[List[str]] = Field(default=None, description="Observed symptoms")
    allergies: Optional[List[str]] = Field(default=None, description="Reported allergies")
    medications: Optional[List[str]] = Field(default=None, description="Patient's current medications")
    past_medical_history: Optional[List[str]] = Field(default=None, description="Relevant past medical history")


class HeentExam(BaseModel):
    head: Optional[str] = Field(default=None, description="Head exam findings")
    face: Optional[str] = Field(default=None, description="Face exam findings")
    eyes: Optional[str] = Field(default=None, description="Eyes exam findings")
    neck: Optional[str] = Field(default=None, description="Neck (HEENT context) exam findings")


class ChestPhysicalExam(BaseModel):
    chest: Optional[str] = Field(default=None, description="Chest inspection / palpation / trauma findings")
    heart_sounds: Optional[str] = Field(default=None, description="Heart sounds / cardiac auscultation")
    lung_sounds: Optional[str] = Field(default=None, description="Lung sounds / respiratory auscultation")


class AbdomenPhysicalExam(BaseModel):
    general: Optional[str] = Field(default=None, description="General abdominal exam findings")


class BackPhysicalExam(BaseModel):
    back: Optional[str] = Field(default=None, description="Back / spine exam findings")


class ExtremitiesPhysicalExam(BaseModel):
    left_arm: Optional[str] = Field(default=None, description="Left upper extremity")
    right_arm: Optional[str] = Field(default=None, description="Right upper extremity")
    left_leg: Optional[str] = Field(default=None, description="Left lower extremity")
    right_leg: Optional[str] = Field(default=None, description="Right lower extremity")


class PhysicalExam(BaseModel):
    """
    Structured secondary survey / physical exam aligned with common ePCR sections.
    Each leaf is a short free-text finding; null when not stated in the transcript.
    """

    mental_status: Optional[str] = Field(default=None, description="Mental status / LOC / orientation / behavior")
    skin: Optional[str] = Field(default=None, description="Skin color, temperature, wounds, diaphoresis, etc.")
    heent: HeentExam = Field(default_factory=HeentExam)
    chest: ChestPhysicalExam = Field(default_factory=ChestPhysicalExam)
    abdomen: AbdomenPhysicalExam = Field(default_factory=AbdomenPhysicalExam)
    back: BackPhysicalExam = Field(default_factory=BackPhysicalExam)
    pelvis_gu_gi: Optional[str] = Field(
        default=None,
        description="Pelvis, genitourinary, and gastrointestinal findings if mentioned",
    )
    extremities: ExtremitiesPhysicalExam = Field(default_factory=ExtremitiesPhysicalExam)
    neurological: Optional[str] = Field(default=None, description="Neurological exam / motor-sensory / cranial nerves if mentioned")


class EPcrExtraction(BaseModel):
    demographics: PatientDemographics = Field(default_factory=PatientDemographics)
    vitals: VitalSigns = Field(default_factory=VitalSigns)
    assessment: AssessmentInfo = Field(default_factory=AssessmentInfo)
    physical_exam: PhysicalExam = Field(
        default_factory=PhysicalExam,
        description="Structured physical exam / secondary survey by body region",
    )
    interventions: Optional[List[str]] = Field(default=None, description="Any medical interventions performed by EMTs")
    narrative: str = Field(
        default="",
        description="A clean, chronological SOAP or CHART narrative report describing the encounter, written in clinical style",
    )
    clinical_tagged_summary: str = Field(
        default="",
        description=(
            "Dense, telegraphic EMS-style summary with section tags. Each section is one or more sentences after an opening tag "
            "(e.g. '<S> 45 y/o ♀ c/o...'). Typical order: <S> subjective; <O> scene/general objective and primary survey cues; "
            "<HEENT>; <CHEST>; <ABD>; <PELVIS>; <BACK>; <L EXT> / <R EXT> for sided extremity findings (use one or both, or an extra "
            "tagged block when upper vs lower extremities need separate paragraphs); <A> assessment; <P> interventions and on-scene care; "
            "<E> en route, reassessment, radio report, and transfer of care. Omit sections not supported by the transcript. "
            "No signature lines, page numbers, or form placeholders."
        ),
    )
    call_summary: str = Field(
        default="",
        description="A concise plain-English paragraph summarizing what happened on this call, written as if briefing a colleague. Avoid clinical jargon where possible.",
    )


class TranscriptionResponse(BaseModel):
    raw_transcript: str
    epcr_data: EPcrExtraction


class PerKeyUsage(BaseModel):
    """Aggregates for one client API key (identified by SHA-256 of the secret)."""

    key_fingerprint_sha256: str
    process_audio_requests: int = Field(
        ge=0,
        description="Authenticated POST /api/v1/process-audio calls (including those that failed validation or Groq).",
    )
    audio_bytes_transcribed: int = Field(
        ge=0,
        description="Total bytes of audio that completed speech-to-text successfully for this key.",
    )
    full_epcr_successes: int = Field(
        ge=0,
        description="Responses that returned 200 with structured ePCR and narrative.",
    )


class UsageReport(BaseModel):
    by_key: list[PerKeyUsage]
