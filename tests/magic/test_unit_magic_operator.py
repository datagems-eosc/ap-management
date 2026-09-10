from pathlib import Path

import pytest
from moma_management.domain.analytical_pattern import AnalyticalPattern
from moma_management.domain.generated.edges.edge_schema import EdgeLabel

from ap_management.internal.graph_utils import (
    WIRING_KEY,
    WIRING_PARAMETER,
    dataflow_inputs,
    iter_operators,
    wired_input_names,
)
from ap_management.services.ap_catalog.catalog import OperatorPort
from ap_management.services.composer import Composer, SimpleComposition
from ap_management.services.magic_operator import (
    INSTRUCTION_INPUT,
    MagicOperatorBuilder,
    MagicOperatorSpec,
)

ASSETS = Path(__file__).parent.parent.parent / "assets"

SPEC = MagicOperatorSpec(
    ap_name="Explain SQL Query",
    ap_description="Explains a SQL query in plain English.",
    instruction="Explain the given SQL query in plain English.",
    input_name="query",
)


class StubLLM:
    """Returns a fixed spec, so these tests exercise graph assembly, not the model."""

    def __init__(self, spec: MagicOperatorSpec = SPEC):
        self.spec = spec
        self.calls: list = []

    def completion(self, messages, response_format, **kwargs):
        self.calls.append(messages)
        return self.spec


@pytest.fixture
def builder() -> MagicOperatorBuilder:
    # moma_svc=None skips remote validation; AnalyticalPattern still runs its own
    # schema + structure + mapping chain at construction.
    return MagicOperatorBuilder(StubLLM(), None)


@pytest.mark.asyncio
async def test_builds_a_valid_single_operator_ap(builder: MagicOperatorBuilder):
    ap, instruction = await builder.build("explain this query")

    assert isinstance(ap, AnalyticalPattern)
    assert instruction == SPEC.instruction
    assert ap.root.properties["name"] == SPEC.ap_name

    operators = list(iter_operators(ap))
    assert len(operators) == 1
    assert set(operators[0].labels) == {"Magic_Operator", "Operator"}

    assert len(ap.edges) == 1
    assert ap.edges[0].labels == [EdgeLabel.consist_of]
    assert str(ap.edges[0].from_) == str(ap.root.id)
    assert str(ap.edges[0].to) == str(operators[0].id)


@pytest.mark.asyncio
async def test_operator_node_matches_the_deployed_contract(builder: MagicOperatorBuilder):
    ap, _ = await builder.build("explain this query")
    operator = next(iter_operators(ap))

    # properties.name is slugified by the AP Executor into the Consul service name,
    # so it must stay the configured name and never vary per task.
    assert operator.properties["name"] == "Magic Operator"

    inputs = {i["name"]: i for i in operator.properties["inputs"]}
    assert set(inputs) == {INSTRUCTION_INPUT, SPEC.input_name}
    assert [o["name"] for o in operator.properties["outputs"]] == ["response"]

    # The instruction is configuration, not dataflow: the Composer must not try to
    # satisfy it from an upstream operator's outputs.
    assert inputs[INSTRUCTION_INPUT][WIRING_KEY] == WIRING_PARAMETER
    assert [i["name"] for i in dataflow_inputs(operator)] == [SPEC.input_name]


@pytest.mark.asyncio
async def test_version_is_omitted_unless_configured():
    """consul-k8s Service Sync cannot set Service.Meta.version, so a pinned version
    would make the operator unresolvable rather than resolved-to-the-wrong-version."""
    ap, _ = await MagicOperatorBuilder(StubLLM(), None).build("t")
    assert "version" not in next(iter_operators(ap)).properties

    ap, _ = await MagicOperatorBuilder(StubLLM(), None, version="2.0.0").build("t")
    assert next(iter_operators(ap)).properties["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_upstream_outputs_are_offered_to_the_model():
    llm = StubLLM()
    await MagicOperatorBuilder(llm, None).build(
        "translate then explain",
        role="Explain the SQL query",
        upstream_outputs=[OperatorPort(name="query", type="string")],
    )

    prompt = llm.calls[0][1]["content"]
    assert "Explain the SQL query" in prompt
    assert "query" in prompt


@pytest.mark.asyncio
async def test_composes_onto_a_catalogue_ap_without_an_llm(builder: MagicOperatorBuilder):
    """Naming the payload input after the upstream output lets SimpleComposition stitch
    the chain, so a mid-chain magic step needs no agentic fallback."""
    nl_to_sql = AnalyticalPattern.model_validate_json(
        (ASSETS / "01_ap_nl_to_sql.json").read_text())
    magic_ap, _ = await builder.build("explain it")

    composed = await Composer(
        strategies=[SimpleComposition()], moma_svc=None
    ).compose(nl_to_sql, magic_ap)

    magic_op = next(
        op for op in iter_operators(composed) if "Magic_Operator" in op.labels)

    # The payload arrives from upstream; only the instruction is left for the caller.
    assert wired_input_names(composed, str(magic_op.id)) == {SPEC.input_name}
