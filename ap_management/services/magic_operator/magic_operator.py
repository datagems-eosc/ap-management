import json
from datetime import date
from logging import getLogger
from typing import List, Optional, Tuple
from uuid import uuid4

from litellm import Message
from moma_management.domain.analytical_pattern import AnalyticalPattern
from pydantic import BaseModel, Field

from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)
from ap_management.internal.graph_utils import WIRING_KEY, WIRING_PARAMETER
from ap_management.internal.llm import LLM
from ap_management.internal.moma_validation import validate_ap
from ap_management.services.ap_catalog.catalog import OperatorPort
from ap_management.services.dataset_catalog.catalog import DatasetSummary

logger = getLogger(__name__)

# Default name of the operator node the builder emits. The AP Executor slugifies this to
# resolve the operator in Consul ("Magic Operator" -> "magic-operator"), so it must match
# a deployed, registered service and cannot vary per task.
DEFAULT_OPERATOR_NAME = "Magic Operator"

# The input carrying the generated instruction. The deployed magic operator's own config
# must declare this input and reference it from its prompt_template -- the executor only
# forwards an operator's declared *inputs*, so node properties would never reach it.
INSTRUCTION_INPUT = "instruction"

# Name of the operator's single output, matching the magic operator's default output_name.
OUTPUT_NAME = "response"


class MagicOperatorSpec(BaseModel):
    """What the LLM decides about a magic step, given the task and its surroundings."""

    ap_name: str = Field(
        description="Short human label for the generated AP, e.g. 'Explain SQL Query'."
    )
    ap_description: str = Field(
        description="One sentence describing what this AP does end-to-end."
    )
    instruction: str = Field(
        description=(
            "The instruction given to the LLM operator at run time. A concrete, "
            "self-contained operation on the input data, written as an imperative."
        )
    )
    input_name: str = Field(
        description=(
            "Name of the operator's payload input. When upstream outputs are given, "
            "copy the name of the upstream output this step consumes, exactly."
        )
    )


class MagicOperatorBuilder:
    """
    Builds a single-operator AP backed by the generic LLM 'magic' operator, for steps no
    catalogued AP covers.
    """

    def __init__(
        self,
        llm: LLM,
        moma_svc: Optional[MomaManagementClient] = None,
        *,
        operator_name: str = DEFAULT_OPERATOR_NAME,
        version: Optional[str] = None,
    ):
        self.llm = llm
        self.moma_svc = moma_svc
        self.operator_name = operator_name
        self.version = version

    async def build(
        self,
        task: str,
        *,
        role: Optional[str] = None,
        upstream_outputs: Optional[List[OperatorPort]] = None,
        datasets: Optional[List[DatasetSummary]] = None,
    ) -> Tuple[AnalyticalPattern, str]:
        """
        Build an AP wrapping one magic operator.

        Args:
            task: The overall natural-language task.
            role: What this particular step must do, when the magic operator is filling a
                gap mid-chain rather than answering the whole task.
            upstream_outputs: The terminal outputs of the preceding AP. Naming the payload
                input after one of them lets SimpleComposition stitch the chain without
                falling through to the LLM-based AgenticComposition.
            datasets: The datasets the plan runs against, so the instruction can refer to
                the actual data.

        Returns:
            The AP, and the generated instruction to pass as the operator's
            `instruction` input value at run time.
        """
        spec = self._generate_spec(task, role, upstream_outputs or [], datasets or [])
        ap = self._assemble(spec)

        ok, errors = await validate_ap(self.moma_svc, ap)
        if not ok:
            raise ValueError(f"The generated magic operator AP is not valid: {errors}")

        logger.info(
            "Built magic operator AP '%s' with input '%s'", spec.ap_name, spec.input_name
        )
        return ap, spec.instruction

    def _generate_spec(
        self,
        task: str,
        role: Optional[str],
        upstream_outputs: List[OperatorPort],
        datasets: List[DatasetSummary],
    ) -> MagicOperatorSpec:
        user_content = f"Task: {task}"
        if role:
            user_content += f"\nThis step must: {role}"
        if upstream_outputs:
            user_content += (
                "\nThe preceding step produces these outputs; the payload input must be "
                "named after the one this step consumes: "
                f"{json.dumps([o.model_dump() for o in upstream_outputs])}"
            )
        else:
            user_content += (
                "\nThis is the first step: the payload input comes straight from the user."
            )
        if datasets:
            user_content += (
                "\nDatasets the AP will run against: "
                f"{json.dumps([d.model_dump() for d in datasets])}"
            )

        return self.llm.completion(
            [
                Message(role="system", content=MAGIC_OPERATOR_PROMPT),
                Message(role="user", content=user_content),
            ],
            response_format=MagicOperatorSpec,
        )

    def _assemble(self, spec: MagicOperatorSpec) -> AnalyticalPattern:
        """Assemble the PG-JSON graph: an AP root and one operator, joined by consist_of."""
        ap_id = uuid4()
        operator_id = uuid4()

        operator_properties = {
            "name": self.operator_name,
            "description": spec.ap_description,
            "step": 1,
            "inputs": [
                {
                    "name": INSTRUCTION_INPUT,
                    "type": "string",
                    "required": True,
                    "default": "",
                    # Supplied at instantiation time from the plan, never wired from an
                    # upstream operator -- so the Composer leaves it alone when chaining.
                    WIRING_KEY: WIRING_PARAMETER,
                },
                {
                    "name": spec.input_name,
                    "type": "string",
                    "required": True,
                    "default": "",
                },
            ],
            "outputs": [
                {"name": OUTPUT_NAME, "type": "string", "required": True, "default": ""}
            ],
        }
        # Pinning a version filters the Consul lookup on Service.Meta.version, which
        # consul-k8s Service Sync cannot set. Only emit it when explicitly configured.
        if self.version:
            operator_properties["version"] = self.version

        return AnalyticalPattern.model_validate({
            "nodes": [
                {
                    "id": str(ap_id),
                    "labels": ["Analytical_Pattern"],
                    "properties": {
                        "name": spec.ap_name,
                        "description": spec.ap_description,
                        "process": "query",
                        "publishedDate": date.today().isoformat(),
                    },
                },
                {
                    "id": str(operator_id),
                    "labels": ["Magic_Operator", "Operator"],
                    "properties": operator_properties,
                },
            ],
            "edges": [
                {
                    "from": str(ap_id),
                    "to": str(operator_id),
                    "labels": ["consist_of"],
                }
            ],
        })


MAGIC_OPERATOR_PROMPT = """
You configure a "magic operator": a generic LLM-backed operator that performs one
transformation on its input, described by an instruction given to it at run time.

You are given a task, optionally the specific step this operator must cover, the outputs
of the preceding step, and the datasets involved. Produce the operator's configuration.

Rules for `instruction`:
- Write one concrete, self-contained imperative operation on the input data, e.g.
  "Explain the given SQL query in plain English, describing what each clause does."
- Describe only this step's transformation, not the whole task, and not the steps
  another operator already handles.
- Do not address the user, ask questions, or describe a goal — describe the operation.
- Refer to the payload input by the name you choose in `input_name`.
- Do not invent facts about the data that aren't stated in the task or the datasets.

Rules for `input_name`:
- When the preceding step's outputs are given, copy the name of the string output this
  step consumes, exactly as written. This lets the two steps be wired together directly.
- Otherwise choose a short, descriptive snake_case name for what the operator consumes.
"""
