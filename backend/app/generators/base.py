from abc import ABC, abstractmethod

from ..engines.models import DependencyInfo, EventData, ExplanationPayload, ProgressResult


class ExplanationGenerator(ABC):
    """Abstraction over explanation generation engines.

    The rule-based generator is the default and is fully offline. An optional
    LLM-backed generator can be enabled as described in docs/LIMITATIONS.md.
    """

    name: str = "abstract"

    @abstractmethod
    def generate(
        self,
        *,
        ticket: dict,
        events: list[EventData],
        progress: ProgressResult,
        evidence,
        deps: list[DependencyInfo],
        now,
        grounding_score: int,
        grounding_breakdown: list[str],
        model_version: str,
        rules_version: str,
    ) -> ExplanationPayload:
        """Build a fully grounded explanation payload."""