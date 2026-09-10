"""
Which operators can run against which datasets.

A dataset's type constrains the operators that can apply to it: a Text-to-SQL operator
is only meaningful against a relational or tabular dataset, not a corpus of PDFs. The
vocabulary of labels below is the one moma-domain generates under
`moma_management/domain/generated/nodes/dataset/`.
"""

from typing import Dict, FrozenSet, Iterable, List

from moma_management.domain.analytical_pattern import AnalyticalPattern
from moma_management.domain.generated.nodes.node_schema import Node

from ap_management.internal.graph_utils import iter_operators, operator_labels
from ap_management.services.dataset_catalog.catalog import DatasetSummary

TABULAR_KINDS = frozenset({"RelationalDatabase", "Table", "CsvSet", "CSV"})

# Operator label fragment (matched case-insensitively as a substring of the operator's
# specialized label) -> the dataset kinds it requires at least one of.
#
# An operator whose label matches nothing here is treated as dataset-agnostic and stays
# compatible with everything: the catalogue is open-ended, and silently dropping an
# unknown operator would be worse than letting the matchmaker judge it.
OPERATOR_KIND_REQUIREMENTS: Dict[str, FrozenSet[str]] = {
    "sql": TABULAR_KINDS,
    "schema_analyzer": TABULAR_KINDS,
    "table": TABULAR_KINDS,
    "column": TABULAR_KINDS,
    "pdf": frozenset({"PdfSet", "PDF"}),
    "ocr": frozenset({"PdfSet", "PDF", "ImageSet", "Image"}),
    "image": frozenset({"ImageSet", "Image"}),
    "video": frozenset({"VideoSet", "Video"}),
}


def required_kinds(operator: Node) -> FrozenSet[str]:
    """
    Return the dataset kinds an operator needs at least one of, or an empty set when the
    operator is dataset-agnostic.
    """
    labels = " ".join(operator_labels(operator)).lower()
    required: set[str] = set()
    for fragment, kinds in OPERATOR_KIND_REQUIREMENTS.items():
        if fragment in labels:
            required |= kinds
    return frozenset(required)


def is_operator_compatible(operator: Node, dataset: DatasetSummary) -> bool:
    """True when the operator can run against the dataset (or is dataset-agnostic)."""
    required = required_kinds(operator)
    return not required or bool(required & set(dataset.kinds))


def compatible_dataset_ids(
    ap: AnalyticalPattern, datasets: Iterable[DatasetSummary]
) -> List[str]:
    """
    Return the ids of the datasets this AP can run against: every one of its operators
    must be compatible with the dataset, since the AP runs as a single chain over it.

    With no datasets given the result is empty -- callers treat "no datasets supplied"
    as "no constraint" rather than reading it from this function.
    """
    operators = list(iter_operators(ap))
    return [
        d.id for d in datasets
        if all(is_operator_compatible(op, d) for op in operators)
    ]


def describe_requirements(ap: AnalyticalPattern) -> str:
    """A human-readable summary of what an AP's operators need, for error messages."""
    parts = []
    for op in iter_operators(ap):
        required = required_kinds(op)
        if required:
            name = (op.properties or {}).get("name", str(op.id))
            parts.append(f"{name} requires one of {sorted(required)}")
    return "; ".join(parts) or "no dataset requirements"
