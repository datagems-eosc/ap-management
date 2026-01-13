import pytest
from deepdiff import DeepDiff
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
    ApTestCase(asset_name="ap_sql_select_with_task", reason="with a task"),
    ApTestCase(
        asset_name="ap_sql_select_without_task", reason="without a task"
    ),
    ApTestCase(
        asset_name="ap_sql_ko_double_root", reason="Two Analytical Pattern nodes", valid=False
    ),
]
# Only the valid tests.
ok_test_cases = list(filter(lambda tc: tc.valid, test_cases))


@pytest.mark.parametrize("case", test_cases, ids=[tc.reason for tc in test_cases])
def test_validate_ap(case: ApTestCase, ap_svc: AnalyticalPatternService):
    """
    Basic validation for an Ap
    """
    ap_plain = load_asset(case.asset_name)
    ap_pgjson = PgJson.model_validate_json(ap_plain)
    errors = ap_svc.validate(ap_pgjson)
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
