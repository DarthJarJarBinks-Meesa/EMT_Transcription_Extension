import asyncio
import io
import json
import logging
import os
import re
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

    def _clean_json_candidate(self, text: str) -> str:
        """
        Normalize common model formatting artifacts before JSON parsing.

        We occasionally see code fences or leading/trailing prose even when
        requesting JSON-only output.
        """
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _parse_and_validate_epcr(self, raw_content: Any) -> EPcrExtraction:
        content = str(raw_content or "").strip()
        if not content:
            raise EpcrExtractionError("Model returned an empty response.")

        cleaned = self._clean_json_candidate(content)
        candidates = [cleaned]

        # Fallback: salvage the first JSON object if extra prose leaked in.
        first_obj_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if first_obj_match:
            candidates.append(first_obj_match.group(0).strip())

        parse_error: Exception | None = None
        for candidate in candidates:
            try:
                extracted_data: Any = json.loads(candidate)
            except json.JSONDecodeError as e:
                parse_error = e
                continue
            if not isinstance(extracted_data, dict):
                raise EpcrExtractionError("Model JSON was not an object.")
            try:
                return EPcrExtraction.model_validate(extracted_data)
            except ValidationError as e:
                raise EpcrExtractionError("Model JSON did not match the ePCR schema.") from e

        raise EpcrExtractionError("Model output was not valid JSON.") from parse_error

    def _fallback_epcr_from_transcript(self, transcript: str) -> EPcrExtraction:
        """
        Last-resort fallback for demo resilience when LLM JSON stays invalid.
        """
        summary = transcript.strip()
        if len(summary) > 700:
            summary = summary[:700].rstrip() + "..."
        tagged = summary[:900].rstrip()
        return EPcrExtraction(
            narrative=summary,
            clinical_tagged_summary=f"<S> {tagged}" if tagged else "<S> No clear subjective details captured.",
            call_summary=summary[:350],
        )

    def _not_stated(self, value: str | None) -> str:
        if value is None or not str(value).strip():
            return "Not stated in transcript."
        return str(value).strip()

    def _not_stated_list(self, value: list[str] | None) -> list[str]:
        if not value:
            return ["Not stated in transcript."]
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        return cleaned or ["Not stated in transcript."]

    def _is_missing(self, value: str | None) -> bool:
        if value is None:
            return True
        s = str(value).strip().lower()
        return not s or s == "not stated in transcript."

    def _extract_first(self, pattern: str, transcript: str, flags: int = re.IGNORECASE) -> str | None:
        match = re.search(pattern, transcript, flags)
        if not match:
            return None
        return " ".join(g for g in match.groups() if g).strip() or None

    def _snippet_for_keyword(self, transcript: str, pattern: str) -> str | None:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if not match:
            return None
        start = max(0, transcript.rfind(".", 0, match.start()) + 1)
        end_dot = transcript.find(".", match.end())
        end = len(transcript) if end_dot == -1 else end_dot + 1
        snippet = transcript[start:end].strip()
        return snippet[:180].strip() if snippet else None

    def _enrich_from_transcript_keywords(self, epcr: EPcrExtraction, transcript: str) -> EPcrExtraction:
        """
        Heuristic rescue layer for high-value fields when LLM extraction misses them.
        """
        t = transcript or ""

        # Demographics
        if self._is_missing(epcr.demographics.age):
            age = self._extract_first(
                r"\b(\d{1,3})\s*(?:-| )?(?:y/o|yo|year(?:s)?(?:\s*|-)?old)\b",
                t,
            )
            if age:
                epcr.demographics.age = f"{age} years"

        if self._is_missing(epcr.demographics.weight):
            weight = self._extract_first(r"\b(\d{2,3})\s*(lb|lbs|pounds|kg)\b", t)
            if weight:
                epcr.demographics.weight = weight

        # Vitals
        if self._is_missing(epcr.vitals.blood_pressure):
            bp = self._extract_first(r"\b(\d{2,3}\s*/\s*\d{2,3})\b", t)
            if not bp:
                over = self._extract_first(
                    r"\b(?:blood pressure|bp)\s*(?:is|:)?\s*(\d{2,3})\s*(?:over)\s*(\d{2,3})\b",
                    t,
                )
                if over:
                    parts = over.split()
                    if len(parts) >= 2:
                        bp = f"{parts[0]}/{parts[1]}"
            if bp:
                epcr.vitals.blood_pressure = bp.replace(" ", "")

        if self._is_missing(epcr.vitals.heart_rate):
            hr = self._extract_first(r"\b(?:heart\s*rate|hr|pulse)\s*(?:is|are|of|:)?\s*(\d{2,3})\b", t)
            if hr:
                epcr.vitals.heart_rate = hr

        if self._is_missing(epcr.vitals.respiratory_rate):
            rr = self._extract_first(r"\b(?:resp(?:iratory)?\s*rate|respirations?|rr)\s*(?:is|are|of|:)?\s*(\d{1,2})\b", t)
            if rr:
                epcr.vitals.respiratory_rate = rr

        if self._is_missing(epcr.vitals.spo2):
            spo2 = self._extract_first(
                r"\b(?:spo2|o2\s*sat(?:uration)?|oxygen\s*saturation)\s*(?:is|:)?\s*(\d{2,3})\s*%?\b",
                t,
            )
            if not spo2:
                spo2 = self._extract_first(r"\b(\d{2,3})\s*%\s*(?:on\s*room\s*air|room\s*air)\b", t)
            if spo2:
                epcr.vitals.spo2 = f"{spo2}%"

        if self._is_missing(epcr.vitals.gcs):
            gcs = self._extract_first(r"\bgcs\s*(?:is|:)?\s*(\d{1,2})\b", t)
            if gcs:
                epcr.vitals.gcs = gcs

        # Organ/exam clues
        if self._is_missing(epcr.physical_exam.chest.lung_sounds):
            lung_match = re.search(
                r"\b(?:lungs?|lung\s*sounds?|breath\s*sounds?)\b.{0,40}\b(clear(?: to auscultation)?|cta|wheez(?:e|ing)?|rhonchi|crackles?)\b",
                t,
                re.IGNORECASE,
            )
            if lung_match:
                token = lung_match.group(1)
                epcr.physical_exam.chest.lung_sounds = token.upper() if token.lower() == "cta" else token

        # Blood loss / bleeding cues
        if self._is_missing(epcr.assessment.chief_complaint):
            if re.search(r"\b(bleed(?:ing)?|blood\s*loss|hemorrhag(?:e|ing)|laceration|lac)\b", t, re.IGNORECASE):
                epcr.assessment.chief_complaint = "Possible bleeding / blood loss event reported."

        if epcr.assessment.symptoms is None:
            epcr.assessment.symptoms = []
        if re.search(r"\b(bleed(?:ing)?|blood\s*loss|hemorrhag(?:e|ing))\b", t, re.IGNORECASE):
            if not any("bleed" in s.lower() or "blood loss" in s.lower() for s in epcr.assessment.symptoms):
                epcr.assessment.symptoms.append("Bleeding / blood loss mentioned in transcript.")

        # ------------------------------------------------------------------
        # One keyword fallback per subfield (broad safety net)
        # ------------------------------------------------------------------
        if self._is_missing(epcr.demographics.name):
            name_line = self._snippet_for_keyword(t, r"\bmy name is|name\b")
            if name_line:
                epcr.demographics.name = name_line
        if self._is_missing(epcr.demographics.gender):
            g = self._extract_first(r"\b(male|female|man|woman)\b", t)
            if g:
                epcr.demographics.gender = g

        if self._is_missing(epcr.assessment.chief_complaint):
            cc_line = self._snippet_for_keyword(t, r"\bc\/o|chief complaint|complaint\b")
            if cc_line:
                epcr.assessment.chief_complaint = cc_line
        if not epcr.assessment.symptoms:
            s_line = self._snippet_for_keyword(t, r"\bsymptom|pain|nausea|dizziness|shortness of breath|sob\b")
            if s_line:
                epcr.assessment.symptoms = [s_line]
        if not epcr.assessment.allergies:
            a_line = self._snippet_for_keyword(t, r"\ballerg(?:y|ies)|nka|no known allergies\b")
            if a_line:
                epcr.assessment.allergies = [a_line]
        if not epcr.assessment.medications:
            m_line = self._snippet_for_keyword(t, r"\bmed(?:s|ications?)|takes\b")
            if m_line:
                epcr.assessment.medications = [m_line]
        if not epcr.assessment.past_medical_history:
            h_line = self._snippet_for_keyword(t, r"\bhistory|pmh|past medical\b")
            if h_line:
                epcr.assessment.past_medical_history = [h_line]

        if self._is_missing(epcr.physical_exam.mental_status):
            ms_line = self._snippet_for_keyword(t, r"\ba&ox?|alert|oriented|gcs|mental status\b")
            if ms_line:
                epcr.physical_exam.mental_status = ms_line
        if self._is_missing(epcr.physical_exam.skin):
            skin_line = self._snippet_for_keyword(t, r"\bskin|pale|warm|cool|diaphoretic|moist|dry\b")
            if skin_line:
                epcr.physical_exam.skin = skin_line

        if self._is_missing(epcr.physical_exam.heent.head):
            head_line = self._snippet_for_keyword(t, r"\bhead|cephalic\b")
            if head_line:
                epcr.physical_exam.heent.head = head_line
        if self._is_missing(epcr.physical_exam.heent.face):
            face_line = self._snippet_for_keyword(t, r"\bface|facial\b")
            if face_line:
                epcr.physical_exam.heent.face = face_line
        if self._is_missing(epcr.physical_exam.heent.eyes):
            eyes_line = self._snippet_for_keyword(t, r"\beyes?|pupils?|perrl|vision\b")
            if eyes_line:
                epcr.physical_exam.heent.eyes = eyes_line
        if self._is_missing(epcr.physical_exam.heent.neck):
            neck_line = self._snippet_for_keyword(t, r"\bneck|jvd|trachea\b")
            if neck_line:
                epcr.physical_exam.heent.neck = neck_line

        if self._is_missing(epcr.physical_exam.chest.chest):
            chest_line = self._snippet_for_keyword(t, r"\bchest|thorax\b")
            if chest_line:
                epcr.physical_exam.chest.chest = chest_line
        if self._is_missing(epcr.physical_exam.chest.heart_sounds):
            heart_line = self._snippet_for_keyword(t, r"\bheart sounds?|cardiac|s1|s2\b")
            if heart_line:
                epcr.physical_exam.chest.heart_sounds = heart_line
        if self._is_missing(epcr.physical_exam.chest.lung_sounds):
            lung_line = self._snippet_for_keyword(t, r"\blung|breath sounds?|wheeze|rhonchi|crackles|cta\b")
            if lung_line:
                epcr.physical_exam.chest.lung_sounds = lung_line

        if self._is_missing(epcr.physical_exam.abdomen.general):
            abd_line = self._snippet_for_keyword(t, r"\babd(?:omen|ominal)?|belly\b")
            if abd_line:
                epcr.physical_exam.abdomen.general = abd_line
        if self._is_missing(epcr.physical_exam.back.back):
            back_line = self._snippet_for_keyword(t, r"\bback|spine\b")
            if back_line:
                epcr.physical_exam.back.back = back_line
        if self._is_missing(epcr.physical_exam.pelvis_gu_gi):
            pelvis_line = self._snippet_for_keyword(t, r"\b(pelvis|gu|gi|urinary|incontinence)\b")
            if pelvis_line:
                epcr.physical_exam.pelvis_gu_gi = pelvis_line
        if self._is_missing(epcr.physical_exam.extremities.left_arm):
            la_line = self._snippet_for_keyword(t, r"\bleft arm|l arm|left upper extremity\b")
            if la_line:
                epcr.physical_exam.extremities.left_arm = la_line
        if self._is_missing(epcr.physical_exam.extremities.right_arm):
            ra_line = self._snippet_for_keyword(t, r"\bright arm|r arm|right upper extremity\b")
            if ra_line:
                epcr.physical_exam.extremities.right_arm = ra_line
        if self._is_missing(epcr.physical_exam.extremities.left_leg):
            ll_line = self._snippet_for_keyword(t, r"\bleft leg|l leg|left lower extremity\b")
            if ll_line:
                epcr.physical_exam.extremities.left_leg = ll_line
        if self._is_missing(epcr.physical_exam.extremities.right_leg):
            rl_line = self._snippet_for_keyword(t, r"\bright leg|r leg|right lower extremity\b")
            if rl_line:
                epcr.physical_exam.extremities.right_leg = rl_line
        if self._is_missing(epcr.physical_exam.neurological):
            neuro_line = self._snippet_for_keyword(t, r"\bneuro|neurologic|numbness|tingling|motor|sensory\b")
            if neuro_line:
                epcr.physical_exam.neurological = neuro_line

        if not epcr.interventions:
            i_line = self._snippet_for_keyword(t, r"\bintervention|treated|administered|given|applied|oxygen|iv\b")
            if i_line:
                epcr.interventions = [i_line]

        return epcr

    def _apply_not_stated_defaults(self, epcr: EPcrExtraction) -> EPcrExtraction:
        # Demographics
        epcr.demographics.name = self._not_stated(epcr.demographics.name)
        epcr.demographics.age = self._not_stated(epcr.demographics.age)
        epcr.demographics.gender = self._not_stated(epcr.demographics.gender)
        epcr.demographics.weight = self._not_stated(epcr.demographics.weight)

        # Vitals
        epcr.vitals.heart_rate = self._not_stated(epcr.vitals.heart_rate)
        epcr.vitals.blood_pressure = self._not_stated(epcr.vitals.blood_pressure)
        epcr.vitals.respiratory_rate = self._not_stated(epcr.vitals.respiratory_rate)
        epcr.vitals.spo2 = self._not_stated(epcr.vitals.spo2)
        epcr.vitals.gcs = self._not_stated(epcr.vitals.gcs)

        # Assessment
        epcr.assessment.chief_complaint = self._not_stated(epcr.assessment.chief_complaint)
        epcr.assessment.symptoms = self._not_stated_list(epcr.assessment.symptoms)
        epcr.assessment.allergies = self._not_stated_list(epcr.assessment.allergies)
        epcr.assessment.medications = self._not_stated_list(epcr.assessment.medications)
        epcr.assessment.past_medical_history = self._not_stated_list(epcr.assessment.past_medical_history)

        # Physical exam - top level
        epcr.physical_exam.mental_status = self._not_stated(epcr.physical_exam.mental_status)
        epcr.physical_exam.skin = self._not_stated(epcr.physical_exam.skin)
        epcr.physical_exam.pelvis_gu_gi = self._not_stated(epcr.physical_exam.pelvis_gu_gi)
        epcr.physical_exam.neurological = self._not_stated(epcr.physical_exam.neurological)

        # Physical exam - nested sections
        epcr.physical_exam.heent.head = self._not_stated(epcr.physical_exam.heent.head)
        epcr.physical_exam.heent.face = self._not_stated(epcr.physical_exam.heent.face)
        epcr.physical_exam.heent.eyes = self._not_stated(epcr.physical_exam.heent.eyes)
        epcr.physical_exam.heent.neck = self._not_stated(epcr.physical_exam.heent.neck)

        epcr.physical_exam.chest.chest = self._not_stated(epcr.physical_exam.chest.chest)
        epcr.physical_exam.chest.heart_sounds = self._not_stated(epcr.physical_exam.chest.heart_sounds)
        epcr.physical_exam.chest.lung_sounds = self._not_stated(epcr.physical_exam.chest.lung_sounds)

        epcr.physical_exam.abdomen.general = self._not_stated(epcr.physical_exam.abdomen.general)
        epcr.physical_exam.back.back = self._not_stated(epcr.physical_exam.back.back)

        epcr.physical_exam.extremities.left_arm = self._not_stated(epcr.physical_exam.extremities.left_arm)
        epcr.physical_exam.extremities.right_arm = self._not_stated(epcr.physical_exam.extremities.right_arm)
        epcr.physical_exam.extremities.left_leg = self._not_stated(epcr.physical_exam.extremities.left_leg)
        epcr.physical_exam.extremities.right_leg = self._not_stated(epcr.physical_exam.extremities.right_leg)

        # Remaining top-level fields
        epcr.interventions = self._not_stated_list(epcr.interventions)
        epcr.narrative = self._not_stated(epcr.narrative)
        epcr.clinical_tagged_summary = self._not_stated(epcr.clinical_tagged_summary)
        epcr.call_summary = self._not_stated(epcr.call_summary)

        return epcr

    def build_best_effort_epcr(self, transcript: str) -> EPcrExtraction:
        """
        Public fallback used when a caller catches EpcrExtractionError.
        """
        fallback = self._fallback_epcr_from_transcript(transcript)
        enriched_fallback = self._enrich_from_transcript_keywords(fallback, transcript)
        return self._apply_not_stated_defaults(enriched_fallback)

    def _extract_sync(self, transcript: str) -> EPcrExtraction:
        """Blocking Groq chat completion (run in a worker thread)."""
        schema_json = EPcrExtraction.model_json_schema()
        system_prompt = f"""
        You are an expert EMS documentation assistant.
        Your task is to take a raw spoken transcript of an EMS medical encounter and extract the relevant clinical information into a precise JSON structure.

        You must output ONLY valid JSON that precisely matches the following JSON schema:
        {json.dumps(schema_json)}

        Populate `physical_exam` with concise findings for each body region when the transcript mentions an exam, observation, or complaint localized to that region.
        Use null for any region not discussed. Prefer short clinical phrases (e.g. "CTA bilaterally", "PERRL", "no edema") over long prose inside each field.

        Generate `clinical_tagged_summary` as a separate string that mimics student PCR style: phrase-based, minimal complete sentences,
        heavy abbreviations (e.g. A&Ox3, PERRL, CTA, SOB, LOC, NC, vis/palp, reg/weak/rapid, x4 quads, ⊕ for intact neuro checks when appropriate).
        Start each logical block with a tag and a space, in clinical order when possible: <S> then <O> then regional exams <HEENT> <CHEST> <ABD> <PELVIS> <BACK>,
        then extremities using <L EXT> and/or <R EXT> (or two tagged blocks when upper and injured lower extremity need separate paragraphs, as in common run reports),
        then <A> <P> <E>. Do not invent findings; omit a tag entirely if there is nothing for that section. Do not include signature lines, page numbers, or blanks.

        You must also generate a highly professional `narrative` field using the standard SOAP or CHART format, and a plain-English `call_summary` as defined in the schema.
        Do not include any text outside the JSON object.
        """

        last_extraction_error: EpcrExtractionError | None = None
        for attempt in (1, 2):
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

            try:
                extracted = self._parse_and_validate_epcr(message.content)
                enriched = self._enrich_from_transcript_keywords(extracted, transcript)
                return self._apply_not_stated_defaults(enriched)
            except EpcrExtractionError as e:
                last_extraction_error = e
                logger.warning(
                    "Structured extraction parse/validation failed on attempt %d/2 (%s)",
                    attempt,
                    type(e).__name__,
                )

        assert last_extraction_error is not None
        logger.warning(
            "Structured extraction failed after retries; returning fallback ePCR object (%s)",
            type(last_extraction_error).__name__,
        )
        return self.build_best_effort_epcr(transcript)

    async def extract_epcr_data(self, transcript: str) -> EPcrExtraction:
        """Extracts structured ePCR data and narrative from the transcript."""
        return await asyncio.to_thread(self._extract_sync, transcript)


def create_groq_service() -> GroqService:
    """Factory for lifespan / tests (patch this to inject a fake service)."""
    return GroqService()
