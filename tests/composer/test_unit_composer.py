import copy
from json import dumps
from typing import Any, Dict

import pytest
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.services.composer.composer import Composer
from tests.ap_test_cases import ApTestCase, _load_ap


# TODO: Remove this once we can integrate the AP ib
def _normalize_graph(ap: AnalyticalPattern) -> Dict[str, Any]:
    """
    Replace each node UUID with a stable key derived from its labels + properties
    so that randomly-generated IDs don't break equality checks.
    """
    raw = ap.model_dump(by_alias=True, mode="json")

    def _node_key(node):
        return (tuple(sorted(node["labels"])), dumps(node.get("properties", {}), sort_keys=True))

    id_to_stable = {node["id"]: str(i) for i, node in enumerate(
        sorted(raw["nodes"], key=_node_key))}

    normalized_nodes = [
        {**node, "id": id_to_stable[node["id"]]}
        for node in raw["nodes"]
    ]

    def _remap(val):
        return id_to_stable.get(val, val)

    normalized_edges = [
        {**edge, "from": _remap(edge["from"]), "to": _remap(edge["to"])}
        for edge in raw["edges"]
    ]

    def _sort_key(x):
        return dumps(x, sort_keys=True)

    return {
        **raw,
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
        copy.deepcopy(case.ap1), copy.deepcopy(case.ap2), case.expected_mappings
    )
    # Check that the output is a valid AP
    AnalyticalPattern.model_validate(mixed_ap)
    assert _normalize_graph(mixed_ap) == _normalize_graph(case.expected_ap)


@pytest.mark.asyncio
async def test_self_composition_no_duplicate_uuids(no_ai_composer: Composer):
    """Composing an AP with a deepcopy of itself must not produce duplicate node UUIDs."""
    # 02_ap_sql_explanation has a single operator with both inputs (sql) and outputs (provenance).
    # Both are type 'string', so SimpleComposition accepts the pairing.
    ap1 = _load_ap("02_ap_sql_explanation.json")
    ap2 = copy.deepcopy(ap1)

    result = await no_ai_composer.compose(ap1, ap2)

    node_ids = [str(node.id) for node in result.nodes]
    assert len(node_ids) == len(
        set(node_ids)), "Duplicate node UUIDs in self-composed AP"
