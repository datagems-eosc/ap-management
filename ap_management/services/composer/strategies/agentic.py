
import logging
from typing import List, Optional, Tuple

# from headroom import compress
from litellm import Message
from pydantic import BaseModel

from ap_management.internal.llm import LLM
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


class AgenticComposition(CompositionStrategy):

    def __init__(self, llm: LLM):
        self.llm = llm

    def is_possible(self, ap1: dict, ap2: dict) -> Tuple[bool, str]:
        # NOTE: We can always (try to) use the agentic strategy
        return True, ""

    def generate_mapping(self, ap1: dict, ap2: dict) -> Tuple[bool, List[Mapping]]:
        ap1_ops = [op for op in ap1["nodes"] if any(
            label.lower() == "operator" for label in op["labels"])]
        ap2_ops = [op for op in ap2["nodes"] if any(
            label.lower() == "operator" for label in op["labels"])]

        user_query = "\n".join([
            f"AP1: {_extract_op_schema(ap1_ops[-1], 'outputs')}",
            f"AP2: {_extract_op_schema(ap2_ops[0], 'inputs')}",
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

        return report.compatible, report.mappings


SYSTEM_PROMPT = """
You are an AP Composition Agent. Map AP1's last operator outputs to AP2's first operator inputs.

Rules:
1. Prefer exact name matches; fall back to semantic equivalence (e.g. "query"→"sql" if both are SQL strings).
2. An output object's field may satisfy an input with a matching type.
3. Ignore unused AP1 outputs. Every required AP2 input needs exactly one source.
4. Type compatibility: string→string ✓, number→number ✓, string→number ✗, object→string ✗, array→string ✗ (ambiguous: cannot determine which element to use).
5. If any required AP2 input cannot be satisfied, the composition is incompatible.

Input: two operators, each with an id and their fields (name + type; properties if object; items if array).
Use each operator's id as node_id in the mapping. Set name to the bare parameter name (e.g. "query"). Format paths as ['outputs']['name'] or ['inputs']['name'].
For nested object fields, extend the path: ['outputs']['payload']['query']; set name to the leaf field name.

Compatible: {"compatible": true, "mappings": [{"source": {"node_id": "<ap1.id>", "name": "query", "path": "['outputs']['query']", "type": "string"}, "destination": {"node_id": "<ap2.id>", "name": "sql", "path": "['inputs']['sql']", "type": "string"}, "reason": "Both represent an SQL query."}]}
Incompatible: {"compatible": false, "reason": "AP2 requires X but AP1 does not produce it."}
"""
