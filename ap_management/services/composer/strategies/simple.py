
from typing import List, Tuple

from ap_management.services.composer.mapping import Mapping, MappingEndpoint

from .strategy import CompositionStrategy


class SimpleComposition(CompositionStrategy):

    def is_possible(self, ap1: dict, ap2: dict) -> Tuple[bool, str]:
        ap_1_ops = [
            op for op in ap1["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]
        ap_2_ops = [
            op for op in ap2["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]

        ap_1_last_op_outputs = ap_1_ops[-1]["properties"]["outputs"]
        ap_2_first_op_inputs = ap_2_ops[0]["properties"]["inputs"]

        if len(ap_1_last_op_outputs) != len(ap_2_first_op_inputs):
            return False, "AP1 last operator outputs and AP2 first operator inputs have different lengths"

        for ap1_last_op_output_param, ap2_first_op_input_param in zip(ap_1_last_op_outputs, ap_2_first_op_inputs):
            # NOTE: This ignores the complex types as return case, ie array or objects
            if ap1_last_op_output_param["type"] != ap2_first_op_input_param["type"]:
                return False, "AP1 last operator outputs and AP2 first operator inputs have different types"

        return True, ""

    def generate_mapping(self, ap1: dict, ap2: dict) -> Tuple[bool, List[Mapping]]:
        ap_1_ops = [
            op for op in ap1["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]
        ap_2_ops = [
            op for op in ap2["nodes"]
            if any(label.lower() == "operator" for label in op["labels"])
        ]
        if not ap_1_ops or not ap_2_ops:
            return False, []
        ap_1_last_op_outputs = ap_1_ops[-1]["properties"]["outputs"]
        ap_2_first_op_inputs = ap_2_ops[0]["properties"]["inputs"]

        mappings = []
        for ap1_last_op_output_param, ap2_first_op_input_param in zip(ap_1_last_op_outputs, ap_2_first_op_inputs):
            mapping = Mapping(
                source=MappingEndpoint(
                    node_id=ap_1_ops[-1]["id"],
                    name=ap1_last_op_output_param["name"],
                    path=f"['outputs']['{ap1_last_op_output_param['name']}']",
                    type=ap1_last_op_output_param["type"],
                ),
                destination=MappingEndpoint(
                    node_id=ap_2_ops[0]["id"],
                    name=ap2_first_op_input_param["name"],
                    path=f"['inputs']['{ap2_first_op_input_param['name']}']",
                    type=ap2_first_op_input_param["type"]
                ),
                confidence=1.0,
                reason="The output type of the last operator of AP1 matches the input type of the first operator of AP2."
            )
            mappings.append(mapping)

        return True, mappings
