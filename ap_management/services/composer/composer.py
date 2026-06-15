import copy
from logging import getLogger
from typing import List, Tuple
from uuid import UUID, uuid4

from kiota_abstractions.api_error import APIError
from moma_management.domain.analytical_pattern import AnalyticalPattern
from moma_management.domain.generated.edges.edge_schema import Edge
from moma_management.domain.generated.nodes.node_schema import Node

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

    async def compose(self, ap1: AnalyticalPattern, ap2: AnalyticalPattern) -> AnalyticalPattern:
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
        ap_1_ops = [op for op in ap1.nodes if any(
            label.lower() == "operator" for label in op.labels)]
        if not ap_1_ops:
            raise CompositionInputError("AP1 has no operators")

        ap_2_ops = [op for op in ap2.nodes if any(
            label.lower() == "operator" for label in op.labels)]
        if not ap_2_ops:
            raise CompositionInputError("AP2 has no operators")

        # Sanity check: operators must expose inputs/outputs as node properties. Old AP syntax is not supported for this.
        ap1_terminal = find_terminal_operator(ap1)
        if "outputs" not in ap1_terminal.properties:
            raise CompositionInputError(
                f"AP1 terminal operator '{ap1_terminal.properties.get('name', str(ap1_terminal.id))}' "
                "has no 'outputs' property"
            )

        ap2_entry = find_entry_operator(ap2)
        if "inputs" not in ap2_entry.properties:
            raise CompositionInputError(
                f"AP2 entry operator '{ap2_entry.properties.get('name', str(ap2_entry.id))}' "
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

    def _select_strategy(self, ap1: AnalyticalPattern, ap2: AnalyticalPattern) -> CompositionStrategy | None:
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

    def _generate_new_nodes_and_edges(self, mapping: Mapping) -> tuple[list[Node], list[Edge]]:
        """
        Generate a ResultType node and the output/input edges that wire it between AP1's source
        operator and AP2's destination operator.
        Args:
            mapping: The mapping between the output of the first AP and the input of the second AP.
        Returns:
            A tuple of (new_nodes, new_edges) to be added to the first AP for stitching.
        """
        return_node_id = uuid4()
        return_type_node = Node(
            id=return_node_id,
            labels=["ResultType", mapping.source.type],
            properties={"name": mapping.source.name},
        )

        result_slot = f"['{mapping.source.name}']"

        output_edge = Edge.model_validate({
            "from": mapping.source.node_id,
            "to": return_node_id,
            "labels": ["output"],
            "properties": {"mapping": {f"to{result_slot}": f"from{mapping.source.path}"}},
        })

        input_edge = Edge.model_validate({
            "from": mapping.destination.node_id,
            "to": return_node_id,
            "labels": ["input"],
            "properties": {"mapping": {f"to{mapping.destination.path}": f"from{result_slot}"}},
        })

        return [return_type_node], [output_edge, input_edge]

    def _stitch(self, ap1: AnalyticalPattern, ap2: AnalyticalPattern, mapping: List[Mapping]) -> AnalyticalPattern:
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
        # This should never happen from the API, but may in testing
        if ap1 is ap2:
            ap2 = copy.deepcopy(ap2)

        if ap1.edges is None:
            ap1.edges = []
        if ap2.edges is None:
            ap2.edges = []

        for m in mapping:
            new_nodes, new_edges = self._generate_new_nodes_and_edges(m)
            ap1.nodes.extend(new_nodes)
            ap1.edges.extend(new_edges)

        # Add "follows" edges from AP2's entry to each AP1 operator that provides output to AP2.
        # If a mapping references a non-terminal AP1 operator, AP2 must explicitly follow it too.
        ap2_entry = find_entry_operator(ap2)
        ap1_source_ids = {m.source.node_id for m in mapping}
        if not ap1_source_ids:
            ap1_source_ids = {str(find_terminal_operator(ap1).id)}
        for source_id in ap1_source_ids:
            ap1.edges.append(Edge.model_validate({
                "from": ap2_entry.id,
                "to": UUID(source_id),
                "labels": ["follows"],
                "properties": {},
            }))

        # Copy all nodes from AP2 to AP1 except for the Analytical Pattern node
        ap1.nodes.extend([
            node for node in ap2.nodes
            if "Analytical_Pattern" not in node.labels
        ])

        # Copy all edges from AP2 to AP1 (consist_of edges will be repointed below).
        # model_copy() prevents the repointing loop from mutating ap2's own Edge objects.
        ap1.edges.extend([e.model_copy() for e in ap2.edges])

        # Change the id of the Analytical Pattern node of AP1 to a new id to avoid conflicts
        ap1_analytical_pattern_node = next(
            node for node in ap1.nodes if "Analytical_Pattern" in node.labels
        )
        ap1_analytical_pattern_node.id = uuid4()

        # Update all "consist_of" edges (from both AP1 and AP2) to point to the new AP node
        for edge in ap1.edges:
            if edge.labels != ["consist_of"]:
                continue
            edge.from_ = ap1_analytical_pattern_node.id

        return ap1

    async def _validate_ap(self, ap: AnalyticalPattern) -> Tuple[bool, List[str]]:
        """
        Validate the given analytical pattern against the MOMA service.
        Args:
            ap: The analytical pattern to be validated.
        Returns:
            A tuple containing a boolean indicating whether the AP is valid or not, and a list of error messages if the AP is invalid.
        """
        body = ValidatePostRequestBody()
        body.additional_data = ap.model_dump(by_alias=True, mode="json")
        try:
            await self.moma_svc.api.v1.aps.validate.post(body=body)
        except APIError as e:
            logger.error(f"Error validating AP: {e}")
            return False, e.additional_data.get("errors", ["Unknown error during AP validation"])

        return True, []
