import re
from typing import Iterator, List, Set

from moma_management.domain.analytical_pattern import AnalyticalPattern
from moma_management.domain.generated.edges.edge_schema import EdgeLabel
from moma_management.domain.generated.nodes.node_schema import Node

# The last bracketed key of a mapping expression: `to['inputs']['sql']` -> `sql`.
# Same convention the Composer writes in _generate_new_nodes_and_edges and the
# AP Executor reads back in ApInstance._last_key.
_LAST_KEY_RE = re.compile(r"\['([^']+)'\]\s*$")

# Marker on an operator's input declaring how its value arrives. An input marked
# "parameter" is configuration supplied at instantiation time (the planner's
# instantiation_parameters, the executor's ApInstance.state) rather than data wired in
# from an upstream operator, so the Composer must not try to satisfy it from AP1's
# outputs. Absent the marker an input is plain dataflow, which is what every catalogued
# operator is today.
WIRING_KEY = "wiring"
WIRING_PARAMETER = "parameter"


def _is_operator(node: Node) -> bool:
    return any(label.lower() == "operator" for label in node.labels)


def iter_operators(ap: AnalyticalPattern) -> Iterator[Node]:
    """Yield every Operator node of ap, in node-list order."""
    yield from (n for n in ap.nodes if _is_operator(n))


def operator_labels(node: Node) -> List[str]:
    """
    Return a node's specialized labels: everything but the generic "Operator" marker.
    e.g. ["Text_To_SQL_Operator", "Operator"] -> ["Text_To_SQL_Operator"].
    """
    return [label for label in node.labels if label.lower() != "operator"]


def dataflow_inputs(operator: Node) -> List[dict]:
    """
    Return the operator's inputs that expect a value wired from an upstream operator,
    i.e. everything not marked as an instantiation-time parameter.
    """
    return [
        i for i in operator.properties.get("inputs", [])
        if i.get(WIRING_KEY) != WIRING_PARAMETER
    ]


def wired_input_names(ap: AnalyticalPattern, operator_id: str) -> Set[str]:
    """
    Return the input names of an operator that are already satisfied by an incoming
    `input` edge, and therefore need no caller-supplied value.

    The AP Executor resolves those from the upstream operator's output at run time
    (ApInstance.resolve_operator_input_values), so suggesting a value for them would
    be pointless -- the wired value overrides it anyway.
    """
    wired: Set[str] = set()
    for edge in ap.edges or []:
        if EdgeLabel.input not in edge.labels or str(edge.to) != str(operator_id):
            continue
        mapping = (edge.properties.mapping if edge.properties else None) or {}
        for target_expr in mapping:
            match = _LAST_KEY_RE.search(target_expr)
            wired.add(match.group(1) if match else target_expr)
    return wired


def find_terminal_operator(ap: AnalyticalPattern) -> Node:
    """
    Return the terminal operator of ap: the one no other operator follows
    (not referenced as `to` in any intra-AP follows edge).

    The composer stores follows edges as `from: later_op → to: earlier_op`, so the
    terminal (last) operator never appears as `to`.
    """
    nodes = ap.nodes
    edges = ap.edges or []
    op_ids = {str(n.id) for n in nodes if _is_operator(n)}
    ops_as_to = {
        str(e.to) for e in edges
        if e.labels == [EdgeLabel.follows] and str(e.from_) in op_ids and str(e.to) in op_ids
    }
    terminals = [n for n in nodes if _is_operator(n) and str(n.id) not in ops_as_to]
    if len(terminals) > 1:
        raise ValueError(
            f"Wrong graph topology. AP has {len(terminals)} terminal operators, expected exactly 1")

    return terminals[0]


def find_entry_operator(ap: AnalyticalPattern) -> Node:
    """
    Return the entry operator of ap: the one that doesn't follow any other
    operator (not referenced as `from` in any intra-AP follows edge).
    """
    nodes = ap.nodes
    edges = ap.edges or []
    op_ids = {str(n.id) for n in nodes if _is_operator(n)}
    ops_as_from = {
        str(e.from_) for e in edges
        if e.labels == [EdgeLabel.follows] and str(e.from_) in op_ids and str(e.to) in op_ids
    }

    entries = [n for n in nodes if _is_operator(n) and str(n.id) not in ops_as_from]
    if len(entries) != 1:
        raise ValueError(
            f"Wrong graph topology. AP has {len(entries)} entry operators, expected exactly 1")

    return entries[0]
