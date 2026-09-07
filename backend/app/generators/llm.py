"""Optional LLM-backed generator.

The application MUST work without any external API keys, so this generator is
never invoked by default. When no provider/API key is configured it gracefully
falls back to the rule-based generator and records that decision in the
grounding breakdown.

Adapting this to a real provider (OpenAI/Gemini/Claude) is documented in
docs/LIMITATIONS.md and docs/CHANGE_CONTROL.md. The structured claim set from
the rule-based engine is the correct input for any LLM prompt, which keeps the
"evidence-first" guarantee.
"""
from ..engines.models import ExplanationPayload
from .rule_based import RuleBasedExplanationGenerator


class LLMExplanationGenerator(RuleBasedExplanationGenerator):
    """Hybrid generator: evidence-first facts, optional LLM re-wording.

    If LLM_PROVIDER/LLM_API_KEY are not configured (the normal case), this
    falls back to the exact rule-based output so the system keeps working.
    """

    name = "llm"

    def __init__(self, provider: str = "", api_key: str = ""):
        self.provider = provider
        self.api_key = api_key

    def generate(self, **kwargs) -> ExplanationPayload:
        if not self.provider or not self.api_key:
            payload = super().generate(**kwargs)
            payload.grounding_breakdown = payload.grounding_breakdown + [
                "LLM provider not configured - fell back to rule-based generation."
            ]
            return payload
        # A provider would be called here. The claim set (payload.claims) is the
        # grounded input and would be sent as-is to avoid hallucination.
        raise NotImplementedError(
            "LLM provider adapter is intentionally not implemented in this offline demo. "
            "See docs/LIMITATIONS.md for the integration contract."
        )