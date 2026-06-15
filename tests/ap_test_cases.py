from pathlib import Path
from typing import List, Optional

from moma_management.domain.analytical_pattern import AnalyticalPattern
from pydantic import BaseModel

from ap_management.services.composer.mapping import Mapping, MappingEndpoint

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_PATH = PROJECT_ROOT / "assets"


class StrategyOutcome(BaseModel):
    # Whether the strategy can be applied (is_possible returns True)
    applicable: bool
    # Whether the strategy should produce a valid mapping (generate_mapping returns True)
    succeeds: bool


class ApTestCase(BaseModel):
    name: str
    description: str = ""
    ap1: AnalyticalPattern
    ap2: AnalyticalPattern
    simple: StrategyOutcome
    agentic: StrategyOutcome
    # Correct mapping
    expected_mappings: List[Mapping]
    expected_ap: Optional[AnalyticalPattern] = None


def _load_ap(filename: str) -> AnalyticalPattern:
    return AnalyticalPattern.model_validate_json((ASSETS_PATH / filename).read_text())


AP_TEST_CASES = [
    ApTestCase(
        name="One input to one output",
        description="Basic case, operator compatibles",
        ap1=_load_ap("01_ap_nl_to_sql.json"),
        ap2=_load_ap("02_ap_sql_explanation.json"),
        simple=StrategyOutcome(applicable=True, succeeds=True),
        agentic=StrategyOutcome(applicable=True, succeeds=True),
        expected_mappings=[
            Mapping(
                source=MappingEndpoint(
                    node_id='1de6e343-6952-4361-a17f-e4a9f1eaeae2',
                    name='query',
                    path="['outputs']['query']",
                    type='string'
                ),
                destination=MappingEndpoint(
                    node_id='68281dc0-9bb6-4caa-8bf8-b7d0054f1729',
                    name='sql',
                    path="['inputs']['sql']",
                    type='string'
                )
            )
        ],
        expected_ap=_load_ap("composed/01_02.json")
    ),
    ApTestCase(
        name="Multiple outputs to one input",
        description="AP1 has two outputs, but only one of them maps to the input of AP2",
        ap1=_load_ap("03_ap_nl_to_sql_two_outputs.json"),
        ap2=_load_ap("02_ap_sql_explanation.json"),
        simple=StrategyOutcome(applicable=False, succeeds=False),
        agentic=StrategyOutcome(applicable=True, succeeds=True),
        expected_mappings=[
            Mapping(
                source=MappingEndpoint(
                    node_id='1de6e343-6952-4361-a17f-e4a9f1eaeae2',
                    name='query',
                    path="['outputs']['query']",
                    type='string'
                ),
                destination=MappingEndpoint(
                    node_id='68281dc0-9bb6-4caa-8bf8-b7d0054f1729',
                    name='sql',
                    path="['inputs']['sql']",
                    type='string'
                )
            )
        ],
        expected_ap=_load_ap("composed/03_02.json")
    ),
    ApTestCase(
        name="Object output to string input",
        description="AP1 has an output which is an object, but only one of its properties maps to the input of AP2",
        ap1=_load_ap("04_ap_nl_to_sql_object_output.json"),
        ap2=_load_ap("02_ap_sql_explanation.json"),
        simple=StrategyOutcome(applicable=False, succeeds=False),
        agentic=StrategyOutcome(applicable=True, succeeds=True),
        expected_mappings=[
            Mapping(
                source=MappingEndpoint(
                    node_id='1de6e343-6952-4361-a17f-e4a9f1eaeae2',
                    name='query',
                    path="['outputs']['payload']['query']",
                    type='string'
                ),
                destination=MappingEndpoint(
                    node_id='68281dc0-9bb6-4caa-8bf8-b7d0054f1729',
                    name='sql',
                    path="['inputs']['sql']",
                    type='string'
                )
            )
        ],
        expected_ap=_load_ap("composed/04_02.json")
    ),
    ApTestCase(
        name="Ambiguous array output to string input",
        description="AP1 output in aray of strings, but AP2 takes in a string. The situation being ambiguous, the agent needs to stop.",
        ap1=_load_ap("05_ap_nl_to_sql_array_output.json"),
        ap2=_load_ap("02_ap_sql_explanation.json"),
        simple=StrategyOutcome(applicable=False, succeeds=False),
        agentic=StrategyOutcome(applicable=True, succeeds=False),
        expected_mappings=[]
    ),
    ApTestCase(
        name="Cross-operator input mapping",
        description="AP2's single operator sources one input from AP1's first operator and another from AP1's second operator.",
        ap1=_load_ap("06_ap_two_op_chain.json"),
        ap2=_load_ap("07_ap_needs_cross_op.json"),
        simple=StrategyOutcome(applicable=False, succeeds=False),
        agentic=StrategyOutcome(applicable=True, succeeds=True),
        expected_mappings=[
            Mapping(
                source=MappingEndpoint(
                    node_id='a6a60000-0000-4000-8000-000000000002',
                    name='query',
                    path="['outputs']['query']",
                    type='string'
                ),
                destination=MappingEndpoint(
                    node_id='a7a70000-0000-4000-8000-000000000002',
                    name='query',
                    path="['inputs']['query']",
                    type='string'
                )
            ),
            Mapping(
                source=MappingEndpoint(
                    node_id='a6a60000-0000-4000-8000-000000000003',
                    name='schema',
                    path="['outputs']['schema']",
                    type='string'
                ),
                destination=MappingEndpoint(
                    node_id='a7a70000-0000-4000-8000-000000000002',
                    name='schema',
                    path="['inputs']['schema']",
                    type='string'
                )
            ),
        ],
        expected_ap=_load_ap("composed/06_07.json")
    ),
    ApTestCase(
        name="Pre-existing links preserved",
        description="AP1 is already a composed AP with ResultType nodes and output/input edges; composing again must not lose those existing edges.",
        ap1=_load_ap("composed/01_02.json"),
        ap2=_load_ap("08_ap_provenance_consumer.json"),
        simple=StrategyOutcome(applicable=True, succeeds=True),
        agentic=StrategyOutcome(applicable=True, succeeds=True),
        expected_mappings=[
            Mapping(
                source=MappingEndpoint(
                    node_id='68281dc0-9bb6-4caa-8bf8-b7d0054f1729',
                    name='provenance',
                    path="['outputs']['provenance']",
                    type='string'
                ),
                destination=MappingEndpoint(
                    node_id='a8a80000-0000-4000-8000-000000000002',
                    name='provenance',
                    path="['inputs']['provenance']",
                    type='string'
                )
            ),
        ],
        expected_ap=_load_ap("composed/01_02_08.json")
    ),
]
