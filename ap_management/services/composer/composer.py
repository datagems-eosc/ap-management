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
        Merge two APs together based on the given mapping by generating new nodes and edges for stitching, copying all nodes and edges from AP2 to AP1 except for the Analytical Pattern node, and updating "consist_of" edges from AP2 to point to the Analytical Pattern node of AP1.
        Args:
            ap1: The first analytical pattern.
            ap2: The second analytical pattern.
            mapping: The mapping between the output of the first AP and the input of the second AP.
        Returns:
            The stitched analytical pattern.
        """
        for m in mapping:
            stitching_result = self._generate_new_nodes_and_edges(m)
            ap1["nodes"].extend(stitching_result["nodes"])
            ap1["edges"].extend(stitching_result["edges"])

        # Add a "follows" edge from the last operator of AP1 to the first operator of AP2
        ap_1_ops = [
            op for op in ap1["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]
        ap_2_ops = [
            op for op in ap2["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]
        ap1["edges"].append({
            "from": ap_2_ops[0]["id"],
            "labels": ["follows"],
            "to": ap_1_ops[-1]["id"],
            "properties": {}
        })

        # Copy all nodes and edges from AP2 to AP1 except for the Analytical Pattern node
        ap1["nodes"].extend([
            node for node in ap2["nodes"]
            if "Analytical_Pattern" not in node["labels"]
        ])

        # Change the id of the Analytical Pattern node of AP1 to a new id to avoid conflicts
        ap1_analytical_pattern_node = next(
            node for node in ap1["nodes"] if "Analytical_Pattern" in node["labels"]
        )
        ap1_analytical_pattern_node["id"] = str(uuid4())

        # Update "consist_of" edges to match the new Analytical Pattern node id
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
