from pathlib import Path

import pytest
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.internal.dataset_compat import (
    compatible_dataset_ids,
    describe_requirements,
    is_operator_compatible,
    required_kinds,
)
from ap_management.internal.graph_utils import iter_operators
from ap_management.services.dataset_catalog import DatasetSummary, LocalDatasetCatalog

ASSETS = Path(__file__).parent.parent.parent / "assets"
RELATIONAL_ID = "d1000000-0000-4000-8000-000000000001"
PDF_ID = "d2000000-0000-4000-8000-000000000001"


@pytest.fixture
def summaries() -> dict[str, DatasetSummary]:
    catalog = LocalDatasetCatalog(ASSETS / "datasets")
    return {
        s.id: s
        for s in (DatasetSummary.from_dataset(d) for d in catalog.catalog)
    }


@pytest.fixture
def nl_to_sql() -> AnalyticalPattern:
    return AnalyticalPattern.model_validate_json(
        (ASSETS / "01_ap_nl_to_sql.json").read_text())


def test_sql_ap_matches_only_the_relational_dataset(nl_to_sql, summaries):
    assert compatible_dataset_ids(nl_to_sql, summaries.values()) == [RELATIONAL_ID]


def test_sql_operator_requires_tabular_data(nl_to_sql, summaries):
    operator = next(iter_operators(nl_to_sql))

    assert "RelationalDatabase" in required_kinds(operator)
    assert is_operator_compatible(operator, summaries[RELATIONAL_ID])
    assert not is_operator_compatible(operator, summaries[PDF_ID])


def test_unknown_operator_is_dataset_agnostic(summaries):
    """An operator whose label matches no rule stays compatible with everything, so a
    newly added operator is never silently dropped from the catalogue."""
    ap = AnalyticalPattern.model_validate({
        "nodes": [
            {
                "id": "f0000000-0000-4000-8000-000000000001",
                "labels": ["Analytical_Pattern"],
                "properties": {"name": "Novel", "description": "d", "process": "query"},
            },
            {
                "id": "f0000000-0000-4000-8000-000000000002",
                "labels": ["Sentiment_Analysis_Operator", "Operator"],
                "properties": {
                    "name": "Sentiment Analysis",
                    "inputs": [{"name": "text", "type": "string"}],
                    "outputs": [{"name": "sentiment", "type": "string"}],
                },
            },
        ],
        "edges": [{
            "from": "f0000000-0000-4000-8000-000000000001",
            "to": "f0000000-0000-4000-8000-000000000002",
            "labels": ["consist_of"],
        }],
    })

    operator = next(iter_operators(ap))
    assert required_kinds(operator) == frozenset()
    assert sorted(compatible_dataset_ids(ap, summaries.values())) == sorted(summaries)
    assert describe_requirements(ap) == "no dataset requirements"


def test_no_datasets_yields_no_compatible_ids(nl_to_sql):
    assert compatible_dataset_ids(nl_to_sql, []) == []
