from typing import Any, List, Protocol, Self

from moma_management.domain.analytical_pattern import AnalyticalPattern
from pydantic import BaseModel

from ap_management.internal.graph_utils import (
    find_entry_operator,
    find_terminal_operator,
)


class OperatorPort(BaseModel):
    name: str
    type: str
    required: bool = True
    default: Any | None = None

    @classmethod
    def from_properties(cls, params: List[dict]) -> List[Self]:
        return [
            cls(name=p["name"], type=p["type"],
                required=p.get("required", True), default=p.get("default"))
            for p in params
        ]


class APSummary(BaseModel):
    id: str
    name: str
    description: str
    entry_inputs: List[OperatorPort]
    terminal_outputs: List[OperatorPort]

    @classmethod
    def from_ap(cls, ap: AnalyticalPattern) -> Self:
        root = ap.root
        entry_op = find_entry_operator(ap)
        terminal_op = find_terminal_operator(ap)

        return APSummary(
            id=str(root.id),
            name=root.properties["name"],
            description=root.properties["description"],
            entry_inputs=OperatorPort.from_properties(
                entry_op.properties.get("inputs", [])),
            terminal_outputs=OperatorPort.from_properties(
                terminal_op.properties.get("outputs", [])),
        )


class APCatalog(Protocol):

    async def search(self, task: str) -> List[AnalyticalPattern]:
        """ Search for Analytical Patterns that match the given task. """
        ...

    async def get(self, id: str) -> AnalyticalPattern:
        """ Retrieve an Analytical Pattern by its ID. """
        ...
