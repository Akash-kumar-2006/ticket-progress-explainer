from ..config import settings
from .baseline import BaselineExplanationGenerator
from .base import ExplanationGenerator
from .llm import LLMExplanationGenerator
from .rule_based import RuleBasedExplanationGenerator


def get_generator(name: str | None = None) -> ExplanationGenerator:
    """Factory. Default is the offline rule-based generator."""
    if name == "baseline":
        return BaselineExplanationGenerator()
    if name == "llm" and settings.llm_provider and settings.llm_api_key:
        return LLMExplanationGenerator(settings.llm_provider, settings.llm_api_key)
    return RuleBasedExplanationGenerator()


def generator_names() -> list[str]:
    return ["rule_based", "baseline", "llm"]