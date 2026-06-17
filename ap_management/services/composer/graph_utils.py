from moma_management.domain.analytical_pattern import AnalyticalPattern
from moma_management.domain.generated.edges.edge_schema import EdgeLabel
from moma_management.domain.generated.nodes.node_schema import Node


def _is_operator(node: Node) -> bool:
    return any(label.lower() == "operator" for label in node.labels)


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
