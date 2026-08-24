from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

class PreVisitSummaryResult(BaseModel):
    urgency: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        description="Assessed triage urgency based on reported symptoms"
    )
    chief_complaint: str = Field(
        description="Concise clinical summary of the patient's primary complaint"
    )
    suggested_questions: List[str] = Field(
        description="Exactly 3 targeted clinical questions for the doctor to ask"
    )

    @field_validator("suggested_questions")
    @classmethod
    def validate_questions_count(cls, v: List[str]) -> List[str]:
        cleaned = [q.strip() for q in v if q and q.strip()]
        if len(cleaned) == 0:
            return [
                "When did these symptoms first begin?",
                "Are symptoms constant or intermittent?",
                "Have you tried any medications or treatments so far?"
            ]
        if len(cleaned) < 3:
            defaults = [
                "When did these symptoms first begin?",
                "Are symptoms constant or intermittent?",
                "Have you noticed any triggers or relieving factors?"
            ]
            for d in defaults:
                if len(cleaned) < 3 and d not in cleaned:
                    cleaned.append(d)
        return cleaned[:3]

class MedicationScheduleItem(BaseModel):
    medication_name: str
    dosage: str
    timing: str = Field(description="e.g. Morning after breakfast, Bedtime")
    instructions: Optional[str] = ""

class PostVisitSummaryResult(BaseModel):
    visit_explanation: str = Field(
        description="Patient-friendly, clear explanation of the diagnosis and consultation"
    )
    medication_schedule: List[MedicationScheduleItem] = Field(
        default_factory=list,
        description="Structured schedule of prescribed medications with timings"
    )
    follow_up_steps: str = Field(
        description="Clear, actionable next steps and warning signs for the patient"
    )
