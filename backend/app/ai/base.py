from abc import ABC, abstractmethod
from typing import Dict, Any
from app.ai.schemas import PreVisitSummaryResult, PostVisitSummaryResult


class LLMProvider(ABC):
    """Abstract base protocol for AI providers."""

    @abstractmethod
    def generate_pre_visit_summary(self, symptoms: str) -> PreVisitSummaryResult:
        """Analyze patient symptoms and generate urgency, chief complaint, and 3 clinical questions."""
        pass

    @abstractmethod
    def generate_post_visit_summary(self, consultation_data: Dict[str, Any]) -> PostVisitSummaryResult:
        """Analyze doctor diagnosis, clinical notes, and prescription to generate patient-friendly summary."""
        pass
