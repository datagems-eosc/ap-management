import pytest
from pydantic import BaseModel

from ap_management.domain import AnalyticalPattern, PgJson
from ap_management.services.analytical_pattern import AnalyticalPatternService
from tests.helpers import load_asset, pretty_deepdiff


class ApTestCase(BaseModel):
    # File name on disk
    asset_name: str
    # Why bother with this case
    reason: str
    # Is this Ap valid ?
    valid: bool = True


test_cases = [
    ApTestCase(
        asset_name="ap_sql_select_without_task", reason="without a task"
    ),
    ApTestCase(asset_name="ap_sql_select_with_task",
               reason="with a task", valid=False),

    ApTestCase(
        asset_name="ap_sql_ko_double_root", reason="Two Analytical Pattern nodes", valid=False
    ),
    ApTestCase(
        asset_name="ap_sql_ko_orphan", reason="Orphan node in graph", valid=False
    ),
]
# Only the valid tests.
ok_test_cases = list(filter(lambda tc: tc.valid, test_cases))


@pytest.mark.asyncio
@pytest.mark.parametrize("case", test_cases, ids=[tc.reason for tc in test_cases])
async def test_validate_ap(case: ApTestCase, ap_svc: AnalyticalPatternService):
    """
    Basic validation for an Ap
    """
    ap_plain = load_asset(case.asset_name)
    ap_pgjson = PgJson.model_validate_json(ap_plain)
    errors = await ap_svc.validate("base_validation_schema.json", ap_pgjson)
    is_valid = len(errors) == 0
    assert is_valid == case.valid


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ok_test_cases, ids=[tc.reason for tc in ok_test_cases])
async def test_store_ap(case: ApTestCase, ap_svc: AnalyticalPatternService):
    sql_ap_plain = load_asset(case.asset_name)
    sql_ap = AnalyticalPattern.model_validate_json(sql_ap_plain)
    await ap_svc.create(sql_ap)


@pytest.mark.asyncio
async def test_get_non_existant_ap(ap_svc: AnalyticalPatternService):
    """
    Trying to get a non existant AP
    """
    ap = await ap_svc.get("i_do_not_exists")
    assert ap is None


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ok_test_cases, ids=[tc.reason for tc in ok_test_cases])
async def test_cycle_ap(case: ApTestCase, ap_svc: AnalyticalPatternService):
    """
    In this context, cycle an ap means storing it in the db, retrieving it, and comparing the result.
    """
    ap_plain = load_asset(case.asset_name)
    origin_ap = AnalyticalPattern.model_validate_json(ap_plain)
    id = await ap_svc.create(origin_ap)
    dest_ap = await ap_svc.get(id)

    # #######################
    # Sanity check
    #########################
    assert dest_ap is not None
    assert len(origin_ap.nodes) == len(dest_ap.nodes)
    assert len(origin_ap.edges) == len(dest_ap.edges)

    # #######################
    # Compare Topology
    #########################

    # Nodes Ids
    origin_nodes_ids = set([n.id for n in origin_ap.nodes])
    dest_nodes_ids = set([n.id for n in dest_ap.nodes])
    assert origin_nodes_ids == dest_nodes_ids

    # Edges Ids
    # From
    origin_edges_from_ids = set([n.from_ for n in origin_ap.edges])
    dest_edges_from_ids = set([n.from_ for n in dest_ap.edges])
    assert origin_edges_from_ids == dest_edges_from_ids
    # To
    origin_edges_to_ids = set([n.to for n in origin_ap.edges])
    dest_edges_to_ids = set([n.to for n in dest_ap.edges])
    assert origin_edges_to_ids == dest_edges_to_ids

    # #######################
    # Deep equality : Compare attributes
    #########################
    diff = origin_ap.difference(dest_ap)
    assert diff == {}, pretty_deepdiff(diff)


@pytest.mark.asyncio
async def test_search_ap(ap_svc: AnalyticalPatternService):
    """
    Store an AP, then search for it with a semantically related query.
    """
    ap_plain = load_asset("ap_sql_select_without_task")
    ap = AnalyticalPattern.model_validate_json(ap_plain)
    await ap_svc.create(ap)

    results = await ap_svc.search("query a dataset", top_k=5)

    assert len(results) > 0
    top_ap, top_score = results[0]
    assert top_ap is not None
    assert 0.0 <= top_score <= 1.0


@pytest.mark.asyncio
async def test_resolve_ap(ap_svc: AnalyticalPatternService):
    """
    Test that a simple query generates a valid Analytical Pattern.
    """
    query = "Discrete Mathematics Recursivity level 2"
    ap, score, created = await ap_svc.resolve(query)
    assert isinstance(ap, AnalyticalPattern)
    assert score is not None
    assert created is True

    # Second call with the same query should find the existing AP
    ap2, score2, created2 = await ap_svc.resolve(query)
    assert ap2.root.id == ap.root.id
    assert score2 is not None
    assert created2 is False
