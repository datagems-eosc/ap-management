import copy
from http.client import HTTPException
from logging import getLogger
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from kiota_abstractions.api_error import APIError

from ap_management.generated.moma_management.api.v1.aps.validate.validate_post_request_body import (
    ValidatePostRequestBody,
)
from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)

from .exceptions import (
    CompositionImpossibleError,
    CompositionInputError,
    CompositionInternalError,
)
from .graph_utils import find_entry_operator, find_terminal_operator
from .mapping import Mapping
from .strategies.strategy import CompositionStrategy

logger = getLogger(__name__)


class Composer:

    def __init__(self, *, strategies: List[CompositionStrategy] = [], moma_svc: MomaManagementClient):
        self.strategies = strategies
        self.moma_svc = moma_svc

    async def compose(self, ap1: Dict[str, Any], ap2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compose two analytical patterns together by finding a mapping between the output of the first AP and the input of the second AP, and stitching them together based on the mapping.
        The mapping can be generated either by a simple rule-based strategy or by an LLM-based strategy.
        Args:
            ap1: The first analytical pattern.
            ap2: The second analytical pattern.
        Returns:
            The composed analytical pattern.
        """
        # Sanity check: Both APs should have at least one operator
        ap_1_ops = [
            op for op in ap1["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]
        if not ap_1_ops:
            raise CompositionInputError("AP1 has no operators")

        ap_2_ops = [
            op for op in ap2["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]
        if not ap_2_ops:
            raise CompositionInputError("AP2 has no operators")

        # Guard: operators must expose inputs/outputs as node properties
        ap1_terminal = find_terminal_operator(ap1)
        if "outputs" not in ap1_terminal.get("properties", {}):
            raise CompositionInputError(
                f"AP1 terminal operator '{ap1_terminal.get('properties', {}).get('name', ap1_terminal['id'])}' "
                "has no 'outputs' property"
            )

        ap2_entry = find_entry_operator(ap2)
        if "inputs" not in ap2_entry.get("properties", {}):
            raise CompositionInputError(
                f"AP2 entry operator '{ap2_entry.get('properties', {}).get('name', ap2_entry['id'])}' "
                "has no 'inputs' property"
            )

        # Find a strategy that can be applied to the given APs
        strategy = self._select_strategy(ap1, ap2)
        if strategy is None:
            raise CompositionInputError(
                "No composition strategy can be applied to the given APs")

        ok, mappings, error = strategy.generate_mapping(ap1, ap2)
        if not ok:
            raise CompositionImpossibleError(error)

        # Stitch the two APs together based on the generated mapping
        composed_ap = self._stitch(ap1, ap2, mappings)

        # And validate it
        if not self.moma_svc:
            logger.warning("No MOMA service provided, skipping AP validation")
            return composed_ap

        ok, errors = await self._validate_ap(composed_ap)
        # TODO: Correction loop
        if not ok:
            raise CompositionInternalError(
                f"The composed AP is not valid: {errors}")

        return composed_ap

    def _select_strategy(self, ap1: Dict[str, Any], ap2: Dict[str, Any]) -> CompositionStrategy | None:
        """
        Select a composition strategy that can be applied to the given APs.
        Args:
            ap1: The first analytical pattern.
            ap2: The second analytical pattern.
        Returns:
            A composition strategy that can be applied to the given APs.
        """
        for s in self.strategies:
            is_possible, reason = s.is_possible(ap1, ap2)
            name = s.__class__.__name__
            if not is_possible:
                logger.debug(f"Strategy {name} cannot be applied: {reason}")
            else:
                logger.info(f"Using {name} for composition")
                return s

        return None

    def _generate_new_nodes_and_edges(self, mapping: Mapping) -> Dict[str, Any]:
        """
        Generate new nodes and edges for stitching two APs together based on the given mapping.
        Args:
            mapping: The mapping between the output of the first AP and the input of the second AP.
        Returns:
            A dictionary containing the new nodes and edges to be added to the first AP for stitching.
        """
        dst_ap = {
            "nodes": [],
            "edges": []
        }
        return_node_id = str(uuid4())
        return_type_node = {
            "id": return_node_id,
            "labels": ["ResultType", f"{mapping.source.type}"],
            "properties": {
                "name": mapping.source.name,
            }
        }
        dst_ap["nodes"].append(return_type_node)

        result_slot = f"['{mapping.source.name}']"

        # Output node of AP1 -> ResultType node
        dst_ap["edges"].append({
            "from": mapping.source.node_id,
            "labels": ["output"],
            "to": return_node_id,
            "properties": {
                "mapping": {
                    f"to{result_slot}": f"from{mapping.source.path}",
                }
            }
        })

        # Input node of AP2 -> ResultType node
        dst_ap["edges"].append({
            "from": mapping.destination.node_id,
            "labels": ["input"],
            "to": return_node_id,
            "properties": {
                "mapping": {
                    f"to{mapping.destination.path}": f"from{result_slot}",
                }
            }
        })

        return dst_ap

    def _stitch(self, ap1: Dict[str, Any], ap2: Dict[str, Any], mapping: List[Mapping]) -> Dict[str, Any]:
        """
        Merge two APs together based on the given mapping by generating new nodes and edges for stitching,
        copying all nodes and edges from AP2 to AP1 except for the Analytical Pattern node, and
        updating "consist_of" edges from AP2 to point to the Analytical Pattern node of AP1.
        Args:
            ap1: The first analytical pattern.
            ap2: The second analytical pattern.
            mapping: The mapping between the output of the first AP and the input of the second AP.
        Returns:
            The stitched analytical pattern.
        """
        # Sanity check: If ap1 and ap2 are pointers to the same object, it would induce corruption as ap1 is modified in place.
        # This should nver happen from the API, but may in testing
        if ap1 is ap2:
            ap2 = copy.deepcopy(ap2)

        for m in mapping:
            stitching_result = self._generate_new_nodes_and_edges(m)
            ap1["nodes"].extend(stitching_result["nodes"])
            ap1["edges"].extend(stitching_result["edges"])

        # Add "follows" edges from AP2's entry to each AP1 operator that provides output to AP2.
        # If a mapping references a non-terminal AP1 operator, AP2 must explicitly follow it too.
        ap2_entry = find_entry_operator(ap2)
        ap1_source_ids = {m.source.node_id for m in mapping}
        if not ap1_source_ids:
            ap1_source_ids = {find_terminal_operator(ap1)["id"]}
        for source_id in ap1_source_ids:
            ap1["edges"].append({
                "from": ap2_entry["id"],
                "labels": ["follows"],
                "to": source_id,
                "properties": {}
            })

        # Copy all nodes from AP2 to AP1 except for the Analytical Pattern node
        ap1["nodes"].extend([
            node for node in ap2["nodes"]
            if "Analytical_Pattern" not in node["labels"]
        ])

        # Copy all edges from AP2 to AP1 (consist_of edges will be repointed below)
        ap1["edges"].extend([{**e} for e in ap2["edges"]])

        # Change the id of the Analytical Pattern node of AP1 to a new id to avoid conflicts
        ap1_analytical_pattern_node = next(
            node for node in ap1["nodes"] if "Analytical_Pattern" in node["labels"]
        )
        ap1_analytical_pattern_node["id"] = str(uuid4())

        # Update all "consist_of" edges (from both AP1 and AP2) to point to the new AP node
        for i, edge in enumerate(ap1["edges"]):
            if edge["labels"] != ["consist_of"]:
                continue
            ap1["edges"][i]["from"] = ap1_analytical_pattern_node["id"]

        return ap1

    async def _validate_ap(self, ap: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate the given analytical pattern by checking for the presence of required nodes and edges, and ensuring that all operators have valid input and output types.
        Args:
            ap: The analytical pattern to be validated.
        Returns:
            A tuple containing a boolean indicating whether the AP is valid or not, and a list of error messages if the AP is invalid.
        """
        body = ValidatePostRequestBody()
        body.additional_data = ap
        try:
            await self.moma_svc.api.v1.aps.validate.post(body=body)
        except APIError as e:
            logger.error(f"Error validating AP: {e}")
            return False, e.additional_data.get("errors", ["Unknown error during AP validation"])

        return True, []
