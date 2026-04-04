from pydantic import BaseModel, Field
from typing import Optional, List

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

class EPcrExtraction(BaseModel):
    demographics: PatientDemographics
    vitals: VitalSigns
    assessment: AssessmentInfo
    interventions: Optional[List[str]] = Field(default=None, description="Any medical interventions performed by EMTs")
    narrative: str = Field(description="A clean, chronological SOAP or CHART narrative report describing the encounter, written in clinical style")
    call_summary: str = Field(description="A concise plain-English paragraph summarizing what happened on this call, written as if briefing a colleague. Avoid clinical jargon where possible.")

class TranscriptionResponse(BaseModel):
    raw_transcript: str
    epcr_data: EPcrExtraction
