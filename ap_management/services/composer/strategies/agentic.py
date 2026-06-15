
import logging
from typing import List, Optional, Tuple

# from headroom import compress
from litellm import Message
from pydantic import BaseModel

from ap_management.internal.llm import LLM
from ap_management.services.composer.graph_utils import find_entry_operator, find_terminal_operator
from ap_management.services.composer.mapping import Mapping, MappingEndpoint

from .strategy import CompositionStrategy

logger = logging.getLogger(__name__)


class ComposeReport(BaseModel):
    # Are the two APs compatible for composition?
    compatible: bool
    # If not compatible, why?
    reason: Optional[str] = None
    # Which outputs of AP1 map to which inputs of AP2, if compatible
    mappings: List[Mapping] = []


def _field_schema(f: dict) -> dict:
    schema = {"name": f["name"], "type": f["type"]}
    if "required" in f:
        schema["required"] = f["required"]
    if "default" in f:
        schema["default"] = f["default"]
    if f.get("type") == "object" and "properties" in f:
        schema["properties"] = f["properties"]
    if f.get("type") == "array" and "items" in f:
        schema["items"] = f["items"]
    return schema


def _extract_op_schema(op: dict, fields_key: str) -> dict:
    return {
        "id": op["id"],
        fields_key: [_field_schema(f) for f in op["properties"][fields_key]],
    }


def _extract_all_ap1_ops_schema(ap: dict) -> list:
    """Return output schemas for every operator in AP1 so the LLM can source from any of them."""
    nodes, edges = ap["nodes"], ap["edges"]
    op_ids = {n["id"] for n in nodes if any(l.lower() == "operator" for l in n["labels"])}
    # Sort by step for a stable, readable ordering
    ops = sorted(
        (n for n in nodes if n["id"] in op_ids),
        key=lambda n: n.get("properties", {}).get("step", 0),
    )
    return [_extract_op_schema(op, "outputs") for op in ops]


class AgenticComposition(CompositionStrategy):

    def __init__(self, llm: LLM):
        self.llm = llm

    def is_possible(self, _ap1: dict, _ap2: dict) -> Tuple[bool, str]:
        # NOTE: We can always (try to) use the agentic strategy
        return True, ""

    def generate_mapping(self, ap1: dict, ap2: dict) -> Tuple[True, List[Mapping], str]:
        ap2_entry = find_entry_operator(ap2)

        user_query = "\n".join([
            f"AP1 operators: {_extract_all_ap1_ops_schema(ap1)}",
            f"AP2: {_extract_op_schema(ap2_entry, 'inputs')}",
        ])

        messages = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=user_query)
        ]

        # compressed = compress([m.model_dump() for m in messages])
        # logger.debug("Compression ratio for LLM input: %.2f%%",
        #              compressed.compression_ratio * 100)

        report = self.llm.completion(
            messages,
            response_format=ComposeReport,
        )

        if not report.compatible:
            logger.info("Composition incompatible: %s", report.reason)

        return report.compatible, report.mappings, report.reason or ""


SYSTEM_PROMPT = """
You are an AP Composition Agent. Map outputs from any of AP1's operators to AP2's first operator inputs.

Rules:
1. Prefer exact name matches; fall back to semantic equivalence (e.g. "query"→"sql" if both are SQL strings).
2. An output object's field may satisfy an input with a matching type.
3. Ignore unused AP1 outputs. Every AP2 input where required=true needs exactly one source from any AP1 operator; inputs where required=false may be left unmapped.
4. Type compatibility: string→string ✓, number→number ✓, boolean→boolean ✓, string→number ✗, object→string ✗, array→string ✗ (ambiguous: cannot determine which element to use), array<T>→array<U> ✗ when T≠U (incompatible item types).
5. If any required AP2 input cannot be satisfied by any AP1 operator, the composition is incompatible.

Input: a list of AP1 operators (each with an id and outputs) and AP2's first operator (with an id and inputs). Fields include name, type, required, default, and properties/items for complex types.
In each mapping, set source.node_id to the id of the specific AP1 operator whose output is used. Set name to the bare parameter name (e.g. "query"). Format paths as ['outputs']['name'] or ['inputs']['name'].
For nested object fields, extend the path: ['outputs']['payload']['query']; set name to the leaf field name.

Compatible (single source): {"compatible": true, "mappings": [{"source": {"node_id": "<ap1_op.id>", "name": "query", "path": "['outputs']['query']", "type": "string"}, "destination": {"node_id": "<ap2.id>", "name": "sql", "path": "['inputs']['sql']", "type": "string"}, "reason": "Both represent an SQL query."}]}
Compatible (multi-source): {"compatible": true, "mappings": [{"source": {"node_id": "<ap1_op_a.id>", ...}, "destination": {...}}, {"source": {"node_id": "<ap1_op_b.id>", ...}, "destination": {...}}]}
Incompatible: {"compatible": false, "reason": "AP2 requires X but no AP1 operator produces it."}
"""
