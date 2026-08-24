import os
import json
import logging
from typing import Dict, Any
import httpx

from app.ai.base import LLMProvider
from app.ai.schemas import PreVisitSummaryResult, PostVisitSummaryResult

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProvider):
    """
    Google Gemini Provider using standard HTTP API with structured JSON output.
    Uses Gemini 1.5 Flash (or customizable via GEMINI_MODEL).
    """

    def __init__(self, api_key: str = None, model: str = None):
        from app.config import settings
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured in .env or environment")
        self.model = (model or os.getenv("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")).strip()
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def _call_gemini_json(self, prompt: str, system_instruction: str) -> Dict[str, Any]:
        params = {"key": self.api_key}
        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            }
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.base_url, params=params, json=payload)
            if response.status_code != 200:
                logger.error(f"Gemini API error ({response.status_code}): {response.text}")
                raise RuntimeError(f"Gemini API returned status {response.status_code}: {response.text}")

            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)

    def generate_pre_visit_summary(self, symptoms: str) -> PreVisitSummaryResult:
        system_instruction = (
            "You are an AI Clinical Assistant for Clinica healthcare portal. "
            "Analyze the patient's symptoms and return a JSON object with: "
            "'urgency' (string: 'LOW', 'MEDIUM', or 'HIGH'), "
            "'chief_complaint' (concise string summary), and "
            "'suggested_questions' (an array of EXACTLY 3 relevant clinical questions for the physician to ask)."
        )
        prompt = f"Patient Symptoms:\n{symptoms}"

        result_dict = self._call_gemini_json(prompt, system_instruction)
        urgency = result_dict.get("urgency", "MEDIUM").upper()
        if urgency not in ("LOW", "MEDIUM", "HIGH"):
            urgency = "MEDIUM"

        questions = result_dict.get("suggested_questions", [])
        if not isinstance(questions, list) or len(questions) != 3:
            questions = [
                "When did these symptoms first begin?",
                "Have you noticed any triggers or worsening factors?",
                "Are you currently taking any prescription or OTC medications?",
            ]

        return PreVisitSummaryResult(
            urgency=urgency,
            chief_complaint=result_dict.get("chief_complaint", "Patient reported clinical symptoms."),
            suggested_questions=questions,
        )

    def generate_post_visit_summary(self, consultation_data: Dict[str, Any]) -> PostVisitSummaryResult:
        system_instruction = (
            "You are an AI Medical Communicator for patients. "
            "Generate a clear, patient-friendly post-visit summary in plain English. "
            "Return a JSON object with: "
            "'visit_explanation' (a 2-3 sentence compassionate, plain English explanation of their diagnosis and assessment), "
            "'medication_schedule' (an array of objects, each with 'medication_name', 'dosage', 'timing', 'instructions'), and "
            "'follow_up_steps' (clear next steps for the patient's recovery and warning signs)."
        )
        prompt = f"Consultation Record:\n{json.dumps(consultation_data, default=str)}"

        result_dict = self._call_gemini_json(prompt, system_instruction)
        return PostVisitSummaryResult(
            visit_explanation=result_dict.get("visit_explanation", f"During your visit, your doctor diagnosed you with {consultation_data.get('diagnosis', 'your current condition')}."),
            medication_schedule=result_dict.get("medication_schedule", []),
            follow_up_steps=result_dict.get("follow_up_steps", consultation_data.get("follow_up_instructions", "Follow standard care guidelines and rest.")),
        )
