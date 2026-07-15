from logging import getLogger
from typing import Any, List

from litellm import Message
from pydantic import BaseModel, Field

from ap_management.internal.llm import LLM

from ..ap_catalog.catalog import OperatorPort

logger = getLogger(__name__)


class SuggestedParameter(OperatorPort):
    """An instantiation parameter, with a value suggested from the task text."""
    suggested_value: Any | None = None


class ParameterValueSuggestion(BaseModel):
    name: str = Field(description="Exact parameter name, copied from the input schema.")
    value: Any = Field(
        description=(
            "The value to use for this parameter, inferred from the task. "
            "Use the parameter's own default if the task doesn't specify anything relevant, "
            "or null if there is no default and nothing in the task applies."
        )
    )


class ParameterValueSuggestions(BaseModel):
    values: List[ParameterValueSuggestion]


class ValueSuggester:
    """Suggests values for an AP's entry-operator parameters based on a natural-language task."""

    def __init__(self, llm: LLM):
        self.llm = llm

    def suggest(self, task: str, parameters: List[OperatorPort]) -> List[SuggestedParameter]:
        """
        Ask the LLM to suggest a value for each given parameter based on the task text.
        Falls back to each parameter's own default if the LLM call fails, so a suggestion
        failure never fails the whole plan.
        """
        if not parameters:
            return []

        messages = [
            Message(role="system", content=SUGGEST_PARAMETERS_PROMPT),
            Message(role="user", content=(
                f"Task: {task}\n"
                f"Parameters: {[p.model_dump() for p in parameters]}"
            )),
        ]

        try:
            suggestions = self.llm.completion(
                messages, response_format=ParameterValueSuggestions)
            values = {v.name: v.value for v in suggestions.values}
        except Exception as e:
            logger.warning(
                "Parameter value suggestion failed, falling back to defaults: %s", e)
            values = {}

        return [
            SuggestedParameter(
                **p.model_dump(), suggested_value=values.get(p.name, p.default))
            for p in parameters
        ]


SUGGEST_PARAMETERS_PROMPT = """
You are a parameter value assistant. You are given a natural-language task and the
typed input parameters of the entry operator of the Analytical Pattern (AP) chosen to
solve that task. Each parameter has: name, type, required, default.

Suggest a concrete value for each parameter by extracting or inferring it from the
task text, so the AP can be instantiated and run immediately.

Rules:
- Copy the parameter's own default when the task doesn't specify or imply anything
  relevant for it.
- If there is no default and nothing in the task applies, use null.
- Never invent facts that aren't stated or clearly implied by the task.
- Return exactly one entry per given parameter, using its exact name.
"""
