import re
from logging import getLogger
from typing import List

from litellm import query
from pydantic import BaseModel, Field

from ap_management.internal.llm import LLM

from ..ap_catalog.catalog import APCatalog, APSummary

logger = getLogger(__name__)


class TaskResolution(BaseModel):
    role: str = Field(
        description="What this AP contributes in the pipeline, e.g. 'Translate NL query to SQL'."
    )
    analytical_pattern_id: str = Field(
        description="The 'id' field from the APSummary returned by search_aps."
    )


class ProblemResolution(BaseModel):
    reasoning: str = Field(
        description=(
            "The Matchmaker's reasoning for the chosen sequence of APs. "
            "This is for human consumption and is not used by the Composer."
        )
    )
    steps: List[TaskResolution] = Field(
        description=(
            "Ordered list of APs to compose sequentially. "
            "steps[0] runs first; steps[-1] runs last. "
            "The Composer wires steps[n].terminal_outputs → steps[n+1].entry_inputs."
        )
    )


class Matchmaker:
    """
    Takes an NL problem and returns an ordered sequence of Analytical Patterns
    that, when composed by the Composer, solve the task.
    """

    def __init__(self, llm: LLM, catalog: APCatalog):
        self.llm = llm
        self.catalog = catalog

    async def _search_aps(self, task: str) -> List[APSummary]:
        """
        Search the AP catalog for Analytical Patterns relevant to the
        given task. Returns a list of relevant APSummary objects, which contain the AP id, name, description,
        """
        aps = await self.catalog.search(task)
        return [APSummary.from_ap(ap) for ap in aps]

    async def resolve(self, task: str) -> ProblemResolution:
        agent = self.llm.create_agent(
            name="Matchmaker",
            instructions=DECOMPOSE_PROMPT,
            tools=[self._search_aps],
        )
        session = agent.create_session()
        response = await agent.run(task, session=session)

        result: ProblemResolution
        try:
            # NOTE: The backend LLMs used doesn't support the responses API.
            # One consequence of this is that using both tools and structured output at the same time will not work.
            # @see https://github.com/BerriAI/litellm/issues/18381
            # Instead, we try to enforce the structured output by parsing the LLM response as JSON.
            # If that fails, we make a second call to the LLM without tools but with the structured output enforced.
            text = response.text
            match = re.search(
                r"```(?:json)?\s*(\{.*?})\s*```", text, re.DOTALL)
            if match:
                text = match.group(1)
            result = ProblemResolution.model_validate_json(text)
        except Exception as e:
            logger.debug(
                f"Could not parse LLM response as JSON: {text}. Retrying with a second call to the LLM.")
            fallback = await agent.run(task, session=session, tools=[], options={"response_format": ProblemResolution})
            result = ProblemResolution.model_validate_json(fallback.text)

        return result


DECOMPOSE_PROMPT = """
You are the Matchmaker, an AI agent that maps a natural-language analytical task to an
ordered sequence of Analytical Patterns (APs) drawn from a catalogue.

## What is an Analytical Pattern?

An Analytical Pattern is a named, reusable operator pipeline. It has:
- A human-readable name and description.
- One **entry operator** (no predecessor): its `entry_inputs` are the data the AP
  expects to receive from outside.
- One **terminal operator** (no successor): its `terminal_outputs` are the data the
  AP produces when done.
- Zero or more intermediate operators chained internally.

You never see the internal operators. The `search_aps` tool exposes only
`entry_inputs` and `terminal_outputs`.

## The `search_aps` tool

`search_aps(query: str) -> List[APSummary]`

Each APSummary has:
  - `id`               — unique identifier; use this exactly in your answer
  - `name`             — short human label
  - `description`      — what the AP does end-to-end
  - `entry_inputs`     — [{name, type, required}] for the entry operator
  - `terminal_outputs` — [{name, type, required}] for the terminal operator

Call `search_aps` as many times as needed with different queries.
Never invent AP ids — only use ids returned by the tool.

## Your goal

Return the **shortest ordered list of APs** that, when the Composer chains them
left-to-right, solves the user's task.

Composition means: the terminal_outputs of AP[n] are wired to the entry_inputs of
AP[n+1]. The Composer handles exact field mapping but requires type compatibility.
Your job is to pick APs where this wiring is plausible.

## I/O compatibility rules

- string → string  ✓
- number → number  ✓
- boolean → boolean  ✓
- object field → field of the same primitive type  ✓  (Composer extracts the field)
- string → number  ✗
- object → string  ✗
- array → string   ✗
- type mismatch     ✗

A required entry_input of AP[n+1] must be satisfiable by at least one
terminal_output of AP[n]. Optional inputs (required=false) may be left unsatisfied.

## When to return empty steps

Return `"steps": []` when no AP directly addresses what the task asks for.
An AP is only a match when its description explicitly covers the task's domain and
intent — not when you can construct a plausible-but-indirect reasoning chain to it.

Examples of reasoning that must be rejected:
- Task: "pinpoint a satellite location" → rejecting "Text to SQL AP" even if satellite
  data could theoretically live in a database. The task never mentions SQL or databases.
- Task: "forecast the weather" → rejecting any SQL or provenance AP even if weather
  data is stored somewhere. The task domain is forecasting, not querying.

If you cannot find an AP whose description directly and obviously matches the stated
task without inventing unstated requirements, output empty steps.

## Reasoning steps

1. Restate the task. Identify the domain and the explicit inputs/outputs the user needs.
2. Call search_aps with the most relevant query.
3. For each candidate AP ask: "Does this AP's description directly address what the
   task asks for, without requiring me to invent context the user never stated?"
   If the answer is no, discard the AP.
4. If a single AP covers the task end-to-end, use it alone.
5. Otherwise, identify the chain of transformations needed. Call search_aps for each
   step. Verify I/O compatibility at each junction before including an AP.
6. Return ProblemResolution with steps ordered first-to-last.
   If no suitable AP exists in the catalogue, return an empty steps list.

## Output format

Your final message MUST be raw JSON only — no markdown fences, no prose, nothing else.

{
  "reasoning": "<your reasoning>",
  "steps": [
    {
      "role": "<one sentence: what this AP contributes>",
      "analytical_pattern_id": "<exact id returned by search_aps>"
    }
  ]
}

steps[0] executes first; steps[-1] executes last.
analytical_pattern_id must be the exact id value returned by search_aps.
"""
