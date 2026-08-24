import os
import logging
from typing import Dict, Any, Optional
from app.ai.base import LLMProvider
from app.ai.schemas import PreVisitSummaryResult, PostVisitSummaryResult
from app.ai.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

class AIService:
    """
    Dedicated AI Clinical Assistant powered exclusively by Google Gemini AI.
    """

    @classmethod
    def get_provider(cls, requested_provider: Optional[str] = None) -> LLMProvider:
        return GeminiProvider()

    @classmethod
    def generate_pre_visit_summary(cls, symptoms: str, provider_name: Optional[str] = None) -> PreVisitSummaryResult:
        provider = cls.get_provider()
        return provider.generate_pre_visit_summary(symptoms)

    @classmethod
    def generate_post_visit_summary(cls, consultation_data: Dict[str, Any], provider_name: Optional[str] = None) -> PostVisitSummaryResult:
        provider = cls.get_provider()
        return provider.generate_post_visit_summary(consultation_data)

