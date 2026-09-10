from pathlib import Path

import pytest
from moma_management.domain.dataset import Dataset

from ap_management.services.dataset_catalog import DatasetSummary, LocalDatasetCatalog
from ap_management.services.dataset_catalog.catalog import (
    MAX_COLUMNS_PER_TABLE,
    MAX_TABLES,
)

RELATIONAL_ID = "d1000000-0000-4000-8000-000000000001"
PDF_ID = "d2000000-0000-4000-8000-000000000001"


@pytest.fixture
def datasets_path() -> Path:
    return Path(__file__).parent.parent.parent / "assets" / "datasets"


@pytest.fixture
def catalog(datasets_path: Path) -> LocalDatasetCatalog:
    return LocalDatasetCatalog(datasets_path)


@pytest.mark.asyncio
async def test_relational_dataset_summary(catalog: LocalDatasetCatalog):
    summary = DatasetSummary.from_dataset(await catalog.get(RELATIONAL_ID))

    assert summary.id == RELATIONAL_ID
    assert summary.name == "University Enrolment Database"
    assert {"RelationalDatabase", "Table"} <= set(summary.kinds)
    assert "postgresql://reader@db.example.org:5432/enrolment" in summary.access_urls

    tables = {t.name: t for t in summary.tables}
    assert set(tables) == {"students", "courses"}
    assert [c.name for c in tables["students"].columns] == ["id", "age", "full_name"]
    assert tables["students"].columns[1].type == "integer"


@pytest.mark.asyncio
async def test_unstructured_dataset_summary_has_no_tables(catalog: LocalDatasetCatalog):
    summary = DatasetSummary.from_dataset(await catalog.get(PDF_ID))

    assert "PdfSet" in summary.kinds
    assert summary.tables == []
    assert "application/pdf" in summary.encoding_formats
    assert "climate" in summary.keywords


@pytest.mark.asyncio
async def test_unknown_dataset_id_raises(catalog: LocalDatasetCatalog):
    with pytest.raises(ValueError):
        await catalog.get("does-not-exist")


def test_wide_dataset_is_capped():
    """A dataset wider than the caps is truncated, so it cannot blow the prompt."""
    table_count = MAX_TABLES + 3
    column_count = MAX_COLUMNS_PER_TABLE + 5

    nodes = [{
        "id": "e0000000-0000-4000-8000-000000000000",
        "labels": ["sc:Dataset"],
        "properties": {"type": "sc:Dataset", "name": "Wide", "description": "d"},
    }]
    edges = []
    for t in range(table_count):
        table_id = f"e0000000-0000-4000-8000-1000000000{t:02d}"
        nodes.append({
            "id": table_id,
            "labels": ["Table", "Data"],
            "properties": {"type": "cr:FileObject", "name": f"t{t}"},
        })
        edges.append({
            "from": "e0000000-0000-4000-8000-000000000000",
            "to": table_id,
            "labels": ["distribution"],
        })
        for c in range(column_count):
            column_id = f"e0000000-0000-4000-8000-2{t:03d}0000{c:04d}"
            nodes.append({
                "id": column_id,
                "labels": ["ColumnTable", "Column"],
                "properties": {"type": "cr:Field", "name": f"c{c}", "dataType": "string"},
            })
            edges.append({"from": table_id, "to": column_id, "labels": ["containedIn"]})

    summary = DatasetSummary.from_dataset(
        Dataset.model_validate({"nodes": nodes, "edges": edges}))

    assert len(summary.tables) == MAX_TABLES
    assert len(summary.tables[0].columns) == MAX_COLUMNS_PER_TABLE
