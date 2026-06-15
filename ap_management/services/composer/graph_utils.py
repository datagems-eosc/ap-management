from typing import Any, Dict


def _is_operator(node: Dict[str, Any]) -> bool:
    return any(label.lower() == "operator" for label in node["labels"])


def find_terminal_operator(ap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return the terminal operator of ap: the one no other operator follows
    (not referenced as `to` in any intra-AP follows edge).

    The composer stores follows edges as `from: later_op → to: earlier_op`, so the
    terminal (last) operator never appears as `to`.  Falls back to the
    highest-step operator when the topology is ambiguous (e.g. single-op APs
    or APs that use the opposite edge direction).
    """
    nodes, edges = ap["nodes"], ap["edges"]
    op_ids = {n["id"] for n in nodes if _is_operator(n)}
    ops_as_to = {
        e["to"] for e in edges
        if e.get("labels") == ["follows"] and e.get("from") in op_ids and e["to"] in op_ids
    }
    terminals = [n for n in nodes if _is_operator(
        n) and n["id"] not in ops_as_to]
    if len(terminals) > 1:
        raise ValueError(
            f"Wrong graph topology. AP has {len(terminals)} terminal operators, expected exactly 1")

    return terminals[0]


def find_entry_operator(ap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return the entry operator of ap: the one that doesn't follow any other
    operator (not referenced as `from` in any intra-AP follows edge).

    Falls back to the lowest-step operator when the topology is ambiguous.
    """
    nodes, edges = ap["nodes"], ap["edges"]
    op_ids = {n["id"] for n in nodes if _is_operator(n)}
    ops_as_from = {
        e["from"] for e in edges
        if e.get("labels") == ["follows"] and e.get("from") in op_ids and e["to"] in op_ids
    }

    entries = [n for n in nodes if _is_operator(
        n) and n["id"] not in ops_as_from]
    if len(entries) != 1:
        raise ValueError(
            f"Wrong graph topology. AP has {len(entries)} entry operators, expected exactly 1")

    return entries[0]
