from json import dumps
from typing import Any, Dict

import pytest

from ap_management.services.composer.composer import Composer
from tests.ap_test_cases import ApTestCase


# TODO: Remove this once we can integrate the AP ib
def _normalize_graph(ap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace each node UUID with a stable key derived from its labels + properties
    so that randomly-generated IDs don't break equality checks.
    """
    def _node_key(node):
        return (tuple(sorted(node["labels"])), dumps(node.get("properties", {}), sort_keys=True))

    id_to_stable = {node["id"]: str(i) for i, node in enumerate(
        sorted(ap["nodes"], key=_node_key))}

    normalized_nodes = [
        {**node, "id": id_to_stable[node["id"]]}
        for node in ap["nodes"]
    ]

    def _remap(val):
        return id_to_stable.get(val, val)

    normalized_edges = [
        {**edge, "from": _remap(edge["from"]), "to": _remap(edge["to"])}
        for edge in ap["edges"]
    ]

    def _sort_key(x):
        return dumps(x, sort_keys=True)

    return {
        **ap,
        "nodes": sorted(normalized_nodes, key=_sort_key),
        "edges": sorted(normalized_edges, key=_sort_key),
    }


def test_stitch(case: ApTestCase, no_ai_composer: Composer):
    """
    Testing that the stitching produces correct output
    """
    if not case.expected_ap:
        pytest.skip("No expected AP provided for this test case.")

    mixed_ap = no_ai_composer._stitch(
        case.ap1, case.ap2, case.expected_mappings
    )
    assert _normalize_graph(mixed_ap) == _normalize_graph(case.expected_ap)
