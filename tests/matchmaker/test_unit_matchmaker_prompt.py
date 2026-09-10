"""The optional prompt sections must not leak into a request that didn't ask for them.

A dataset-free request that still saw the datasets rules would be told to "reject any AP
whose compatible_dataset_ids is empty" while every AP it is shown has exactly that --
a contradiction that pushes the model toward returning no steps at all.
"""
from pathlib import Path

import pytest
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.services.ap_catalog.catalog import APSummary
from ap_management.services.dataset_catalog import DatasetSummary, LocalDatasetCatalog
from ap_management.services.matchmaker.matchmaker import (
    DECOMPOSE_PROMPT,
    MAGIC_STEP_SENTINEL,
    AnnotatedAPSummary,
    Matchmaker,
    _system_prompt,
)

ASSETS = Path(__file__).parent.parent.parent / "assets"


@pytest.mark.parametrize("has_datasets,allow_magic", [(False, False), (True, False),
                                                      (False, True), (True, True)])
def test_sections_appear_only_when_they_apply(has_datasets: bool, allow_magic: bool):
    prompt = _system_prompt(has_datasets, allow_magic)

    assert ("compatible_dataset_ids" in prompt) is has_datasets
    assert ("## Datasets" in prompt) is has_datasets
    assert (MAGIC_STEP_SENTINEL in prompt) is allow_magic


def test_plain_prompt_is_the_base_prompt():
    assert _system_prompt(False, False) == DECOMPOSE_PROMPT


@pytest.mark.asyncio
async def test_search_aps_omits_the_field_without_datasets():
    """Without datasets there is nothing to be compatible with, so the field is absent
    rather than an empty list the model would read as 'incompatible with everything'."""
    catalog = _StubCatalog()

    plain = await _run_search(catalog, datasets=[])
    assert plain
    assert all(type(s) is APSummary for s in plain)
    assert all("compatible_dataset_ids" not in s.model_dump() for s in plain)

    datasets = [DatasetSummary.from_dataset(d)
                for d in LocalDatasetCatalog(ASSETS / "datasets").catalog]
    annotated = await _run_search(catalog, datasets=datasets)
    assert all(isinstance(s, AnnotatedAPSummary) for s in annotated)
    # The catalogued AP is a SQL one: it matches the relational dataset, not the PDF one.
    assert len(annotated[0].compatible_dataset_ids) == 1


class _StubCatalog:
    def __init__(self):
        self._aps = [AnalyticalPattern.model_validate_json(
            (ASSETS / "01_ap_nl_to_sql.json").read_text())]

    async def search(self, task: str):
        return self._aps

    async def get(self, id: str):
        return self._aps[0]


async def _run_search(catalog, datasets):
    """Drive the tool closure the way the agent would, without an LLM."""
    captured = {}

    class _StubLLM:
        def create_agent(self, name, instructions, tools=None, **kw):
            captured["tool"] = tools[0]
            raise _Stop

    class _Stop(Exception):
        pass

    try:
        await Matchmaker(_StubLLM(), catalog).resolve("t", datasets)
    except Exception:
        pass
    return await captured["tool"]("t")
