import json
from logging import getLogger
from typing import Any, List

from litellm import Message
from pydantic import BaseModel, Field

from ap_management.internal.llm import LLM
from ap_management.services.dataset_catalog.catalog import DatasetSummary

from ..ap_catalog.catalog import OperatorPort

logger = getLogger(__name__)


class SuggestedParameter(OperatorPort):
    """An instantiation parameter, with a value suggested from the task text."""

    suggested_value: Any | None = None
    # The operator node this parameter belongs to. The AP Executor keys its runtime state
    # by operator node id (ApInstance.state is {node_id: {name: value}}), so a flat list of
    # names would be ambiguous as soon as an AP has more than one operator.
    operator_id: str = ""
    operator_name: str = ""


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
    """Suggests values for an AP operator's parameters based on a natural-language task."""

    def __init__(self, llm: LLM):
        self.llm = llm

    def suggest(
        self,
        task: str,
        parameters: List[OperatorPort],
        *,
        datasets: List[DatasetSummary] | None = None,
        operator_id: str = "",
        operator_name: str = "",
    ) -> List[SuggestedParameter]:
        """
        Ask the LLM to suggest a value for each given parameter based on the task text and,
        when available, the datasets the AP will run against.

        Falls back to each parameter's own default if the LLM call fails, so a suggestion
        failure never fails the whole plan.
        """
        if not parameters:
            return []

        user_content = (
            f"Task: {task}\n"
            f"Operator: {operator_name or 'unknown'}\n"
            f"Parameters: {[p.model_dump() for p in parameters]}"
        )
        if datasets:
            user_content += (
                "\nDatasets the AP will run against: "
                f"{json.dumps([d.model_dump() for d in datasets])}"
            )

        messages = [
            Message(role="system", content=SUGGEST_PARAMETERS_PROMPT),
            Message(role="user", content=user_content),
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
                **p.model_dump(),
                suggested_value=values.get(p.name, p.default),
                operator_id=operator_id,
                operator_name=operator_name,
            )
            for p in parameters
        ]


SUGGEST_PARAMETERS_PROMPT = """
You are a parameter value assistant. You are given a natural-language task and the
typed input parameters of one operator of the Analytical Pattern (AP) chosen to solve
that task. Each parameter has: name, type, required, default.

You may also be given the datasets the AP will run against. Each dataset has: id, name,
description, kinds (the kind of data it holds), keywords, encoding_formats, access_urls
(connection strings or content URLs) and tables (name + columns).

Suggest a concrete value for each parameter by extracting or inferring it from the
task text and the datasets, so the AP can be instantiated and run immediately.

Rules:
- When a parameter names a connection, database, URL, path, table or column, take its
  value from the datasets (access_urls, tables[].name, tables[].columns[].name) rather
  than inventing one. Prefer the dataset whose kinds match what the parameter implies.
- Copy the parameter's own default when neither the task nor the datasets specify or
  imply anything relevant for it.
- If there is no default and nothing applies, use null.
- Never invent facts that aren't stated or clearly implied by the task or the datasets.
- Return exactly one entry per given parameter, using its exact name.
"""
