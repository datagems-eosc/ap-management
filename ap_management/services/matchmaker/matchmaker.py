import json
import re
from logging import getLogger
from typing import List

from pydantic import BaseModel, Field

from ap_management.internal.dataset_compat import compatible_dataset_ids
from ap_management.internal.llm import LLM
from ap_management.services.dataset_catalog.catalog import DatasetSummary

from ..ap_catalog.catalog import APCatalog, APSummary

logger = getLogger(__name__)

# The id the matchmaker returns for a step no catalogued AP covers. The planner turns it
# into a magic operator; it is only ever offered to the LLM when magic is allowed.
MAGIC_STEP_SENTINEL = "magic"


class AnnotatedAPSummary(APSummary):
    """An APSummary carrying which of the caller's datasets it can actually run against."""

    compatible_dataset_ids: List[str] = []


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

    async def resolve(
        self,
        task: str,
        datasets: List[DatasetSummary] | None = None,
        *,
        allow_magic_operator: bool = False,
    ) -> ProblemResolution:
        datasets = datasets or []

        async def search_aps(task: str) -> List[APSummary]:
            """
            Search the AP catalog for Analytical Patterns relevant to the
            given task. Returns a list of relevant APSummary objects, which contain the AP id, name, description,
            and which of the available datasets each AP can run against.
            """
            aps = await self.catalog.search(task)
            if not datasets:
                # With no datasets to check against, an empty compatible_dataset_ids on
                # every result would read as "incompatible with everything" -- omit it.
                return [APSummary.from_ap(ap) for ap in aps]
            return [
                AnnotatedAPSummary(
                    **APSummary.from_ap(ap).model_dump(),
                    compatible_dataset_ids=compatible_dataset_ids(ap, datasets),
                )
                for ap in aps
            ]

        agent = self.llm.create_agent(
            name="Matchmaker",
            instructions=_system_prompt(bool(datasets), allow_magic_operator),
            tools=[search_aps],
        )
        session = agent.create_session()
        prompt = _user_prompt(task, datasets)
        response = await agent.run(prompt, session=session)

        result: ProblemResolution
        text = ""
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
        except Exception:
            logger.debug(
                f"Could not parse LLM response as JSON: {text}. Retrying with a second call to the LLM.")
            fallback = await agent.run(prompt, session=session, tools=[], options={"response_format": ProblemResolution})
            result = ProblemResolution.model_validate_json(fallback.text)

        return result


def _user_prompt(task: str, datasets: List[DatasetSummary]) -> str:
    """Datasets go in the user message, not the instructions, so the system prompt stays
    static and cacheable."""
    if not datasets:
        return task
    return (
        f"{task}\n\nAvailable datasets:\n"
        f"{json.dumps([d.model_dump() for d in datasets], indent=2)}"
    )


def _system_prompt(has_datasets: bool, allow_magic_operator: bool) -> str:
    """The base decomposition prompt, plus the dataset and magic-operator sections only
    when the request actually uses them -- so a plain request gets byte-identical
    instructions to what it got before either feature existed."""
    prompt = DECOMPOSE_PROMPT
    if has_datasets:
        prompt += DATASETS_PROMPT_SECTION
    if allow_magic_operator:
        prompt += MAGIC_OPERATOR_PROMPT_SECTION
    return prompt


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


DATASETS_PROMPT_SECTION = """
## Datasets

The user message lists the datasets the plan must run against. Each dataset has an
`id`, a `name`, a `description`, `kinds` (the kind of data it holds, e.g.
`RelationalDatabase`, `PdfSet`), `keywords`, `encoding_formats`, `access_urls` and,
for tabular data, `tables` with their columns.

A dataset's kind determines which operators can apply to it — SQL operators need a
relational or tabular dataset, PDF operators need a document set, and so on. That check
is already done for you: each APSummary's `compatible_dataset_ids` lists the datasets it
can actually run against.

Rules:
- Reject any AP whose `compatible_dataset_ids` is empty. It cannot run on this data,
  however well its description matches the words of the task.
- Prefer APs compatible with the datasets that best match the task's subject.
- When several datasets are given, different steps of the chain may read from different
  datasets. The chain itself stays linear — one AP after another, no branching.
"""


MAGIC_OPERATOR_PROMPT_SECTION = f"""
## The magic operator

For this request you may also use a **magic operator**: a generic LLM-backed operator
that can be instructed to perform any single transformation the catalogue does not cover.

To use it, emit a step whose `analytical_pattern_id` is exactly `"{MAGIC_STEP_SENTINEL}"`
and whose `role` describes, in one precise sentence, the transformation that step must
perform. The role is turned into the operator's instruction, so write it as a concrete
operation on data ("Explain the given SQL query in plain English"), not as a vague goal
("help the user understand").

Rules:
- Prefer a real AP whenever one covers the step. The magic operator is a fallback for a
  genuine gap, not a shortcut around searching the catalogue.
- Call `search_aps` first, and only fall back to the magic operator for steps no result
  covers.
- A magic step takes a single input from the previous step's terminal_outputs (or, if it
  is the first step, from the user's task) and produces one string output.
- A magic step may be the only step, when nothing in the catalogue addresses the task.
- Do not use more than one magic step in a row: collapse consecutive gaps into a single
  magic step whose role describes the whole transformation.
"""
