from typing import List, Tuple

from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.internal.graph_utils import (
    find_entry_operator,
    find_terminal_operator,
)
from ap_management.services.composer.mapping import Mapping, MappingEndpoint

from .strategy import CompositionStrategy


class SimpleComposition(CompositionStrategy):

    def is_possible(self, ap1: AnalyticalPattern, ap2: AnalyticalPattern) -> Tuple[bool, str]:
        ap1_terminal = find_terminal_operator(ap1)
        ap2_entry = find_entry_operator(ap2)

        ap1_outputs = ap1_terminal.properties.get("outputs")
        ap2_inputs = ap2_entry.properties.get("inputs")

        if ap1_outputs is None:
            return False, "AP1 terminal operator has no 'outputs' property"
        if ap2_inputs is None:
            return False, "AP2 entry operator has no 'inputs' property"

        if len(ap1_outputs) != len(ap2_inputs):
            return False, "AP1 last operator outputs and AP2 first operator inputs have different lengths"

        for out_param, in_param in zip(ap1_outputs, ap2_inputs):
            # NOTE: This ignores the complex types as return case, ie array or objects
            if out_param["type"] != in_param["type"]:
                return False, "AP1 last operator outputs and AP2 first operator inputs have different types"

        return True, ""

    def generate_mapping(self, ap1: AnalyticalPattern, ap2: AnalyticalPattern) -> Tuple[True, List[Mapping], str]:
        ap1_terminal = find_terminal_operator(ap1)
        ap2_entry = find_entry_operator(ap2)

        ap1_outputs = ap1_terminal.properties.get("outputs", [])
        ap2_inputs = ap2_entry.properties.get("inputs", [])

        if not ap1_outputs or not ap2_inputs:
            return False, [], "No outputs or inputs to map"

        mappings = []
        for out_param, in_param in zip(ap1_outputs, ap2_inputs):
            mapping = Mapping(
                source=MappingEndpoint(
                    node_id=str(ap1_terminal.id),
                    name=out_param["name"],
                    path=f"['outputs']['{out_param['name']}']",
                    type=out_param["type"],
                ),
                destination=MappingEndpoint(
                    node_id=str(ap2_entry.id),
                    name=in_param["name"],
                    path=f"['inputs']['{in_param['name']}']",
                    type=in_param["type"]
                ),
                confidence=1.0,
                reason="The output type of the last operator of AP1 matches the input type of the first operator of AP2."
            )
            mappings.append(mapping)

        return True, mappings, ""
