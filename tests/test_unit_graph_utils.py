from pathlib import Path

import pytest
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.internal.graph_utils import (
    WIRING_KEY,
    WIRING_PARAMETER,
    dataflow_inputs,
    find_entry_operator,
    find_terminal_operator,
    iter_operators,
    operator_labels,
    wired_input_names,
)

ASSETS = Path(__file__).parent.parent / "assets"


@pytest.fixture
def two_op_chain() -> AnalyticalPattern:
    return AnalyticalPattern.model_validate_json(
        (ASSETS / "06_ap_two_op_chain.json").read_text())


def test_iter_operators_skips_non_operator_nodes(two_op_chain):
    names = [op.properties["name"] for op in iter_operators(two_op_chain)]
    assert names == ["Text to SQL", "Schema Analyzer"]


def test_operator_labels_drops_the_generic_marker(two_op_chain):
    entry = find_entry_operator(two_op_chain)
    assert operator_labels(entry) == ["Text_To_SQL_Operator"]


def test_wired_input_names_is_empty_without_input_edges(two_op_chain):
    """Nothing is wired in an uncomposed AP: every input needs a caller-supplied value."""
    for op in iter_operators(two_op_chain):
        assert wired_input_names(two_op_chain, str(op.id)) == set()


def test_wired_input_names_reads_composed_mapping_edges():
    """A composed AP wires the consumer's input through a ResultType hop; the helper must
    read the target name out of the mapping expression `to['inputs']['<name>']`."""
    composed = AnalyticalPattern.model_validate_json(
        (ASSETS / "composed" / "01_02.json").read_text())

    terminal = find_terminal_operator(composed)
    wired = wired_input_names(composed, str(terminal.id))

    declared = {i["name"] for i in terminal.properties.get("inputs", [])}
    assert wired
    assert wired <= declared


def test_dataflow_inputs_excludes_parameter_inputs():
    ap = AnalyticalPattern.model_validate({
        "nodes": [
            {
                "id": "aa000000-0000-4000-8000-000000000001",
                "labels": ["Analytical_Pattern"],
                "properties": {"name": "n", "description": "d", "process": "query"},
            },
            {
                "id": "aa000000-0000-4000-8000-000000000002",
                "labels": ["Some_Operator", "Operator"],
                "properties": {
                    "name": "Some Operator",
                    "inputs": [
                        {"name": "cfg", "type": "string",
                         WIRING_KEY: WIRING_PARAMETER},
                        {"name": "payload", "type": "string"},
                    ],
                    "outputs": [{"name": "out", "type": "string"}],
                },
            },
        ],
        "edges": [{
            "from": "aa000000-0000-4000-8000-000000000001",
            "to": "aa000000-0000-4000-8000-000000000002",
            "labels": ["consist_of"],
        }],
    })

    operator = next(iter_operators(ap))

    assert [i["name"] for i in dataflow_inputs(operator)] == ["payload"]
