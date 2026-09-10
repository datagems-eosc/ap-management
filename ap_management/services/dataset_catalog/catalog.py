from typing import Iterable, List, Protocol, Self

from moma_management.domain.dataset import Dataset
from moma_management.domain.generated.nodes.node_schema import Node
from pydantic import BaseModel

# The root node label of a Dataset graph (moma_management.domain.dataset.Dataset._root_label).
ROOT_LABEL = "sc:Dataset"

# Labels of nodes that describe a tabular structure, and of their column children.
_TABULAR_LABELS = frozenset({"Table", "CSV"})
_COLUMN_LABELS = frozenset({"Column", "ColumnTable", "ColumnCSV"})

# A dataset subgraph can carry one node per column and several statistics nodes per
# column, which is far more than an LLM needs -- or than a prompt can afford -- to
# decide whether an operator applies. Project only the shape, and cap it.
MAX_TABLES = 10
MAX_COLUMNS_PER_TABLE = 25


class ColumnSummary(BaseModel):
    name: str
    type: str | None = None


class TableSummary(BaseModel):
    name: str
    columns: List[ColumnSummary]


class DatasetSummary(BaseModel):
    """
    The LLM-facing projection of a Dataset graph: enough to decide which operators can
    apply to it and to bind an operator's connection/table parameters, and no more.
    """

    id: str
    name: str
    description: str = ""
    # The data-node labels present in the graph, e.g. ["RelationalDatabase", "Table"].
    # This is what determines operator compatibility (see internal/dataset_compat.py).
    kinds: List[str] = []
    keywords: List[str] = []
    encoding_formats: List[str] = []
    # Where the data actually lives, when the graph says so: a connection string for a
    # RelationalDatabase, a contentUrl for a file-backed distribution.
    access_urls: List[str] = []
    # Empty for unstructured datasets (PDF/text/image/video sets).
    tables: List[TableSummary] = []

    @classmethod
    def from_dataset(cls, ds: Dataset) -> Self:
        root = next(n for n in ds.nodes if ROOT_LABEL in n.labels)
        props = root.properties or {}

        tables = _summarize_tables(ds)

        return cls(
            id=str(root.id),
            name=props.get("name", ""),
            description=props.get("description", ""),
            kinds=list(dict.fromkeys(
                label for node in ds.nodes for label in node.labels
                if label != ROOT_LABEL
            )),
            keywords=props.get("keywords") or [],
            encoding_formats=_distinct(
                node.properties.get("encodingFormat")
                for node in ds.nodes
                if node.properties
            ),
            access_urls=_distinct(
                (node.properties or {}).get("connectionString")
                or (node.properties or {}).get("contentUrl")
                for node in ds.nodes
                if ROOT_LABEL not in node.labels
            ),
            tables=tables[:MAX_TABLES],
        )


def _summarize_tables(ds: Dataset) -> List[TableSummary]:
    """
    Build one TableSummary per tabular node, reading its columns from the
    `containedIn` edges that point at Column nodes (see the schema's
    edge_constraints.json: Table -[containedIn]-> ColumnTable, CSV -> ColumnCSV).
    """
    by_id = {str(n.id): n for n in ds.nodes}
    columns_of: dict[str, List[Node]] = {}
    for edge in ds.edges or []:
        source = by_id.get(str(edge.from_))
        target = by_id.get(str(edge.to))
        if not source or not target:
            continue
        if _TABULAR_LABELS.isdisjoint(source.labels) or _COLUMN_LABELS.isdisjoint(target.labels):
            continue
        columns_of.setdefault(str(source.id), []).append(target)

    summaries: List[TableSummary] = []
    for node in ds.nodes:
        if _TABULAR_LABELS.isdisjoint(node.labels):
            continue
        columns = columns_of.get(str(node.id), [])
        summaries.append(TableSummary(
            name=(node.properties or {}).get("name", ""),
            columns=[
                ColumnSummary(
                    name=(c.properties or {}).get("name", ""),
                    type=(c.properties or {}).get("dataType"),
                )
                for c in columns[:MAX_COLUMNS_PER_TABLE]
            ],
        ))
    return summaries


def _distinct(values: Iterable) -> List[str]:
    """Preserve order, drop empties and duplicates."""
    return list(dict.fromkeys(str(v) for v in values if v))


class DatasetCatalog(Protocol):

    async def get(self, id: str) -> Dataset:
        """Retrieve a Dataset by its ID."""
        ...
