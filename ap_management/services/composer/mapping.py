from typing import Optional

from pydantic import BaseModel


class MappingEndpoint(BaseModel):
    # The id of the node in the graph, e.g. the operator node id
    node_id: Optional[str] = None
    # The bare parameter name, e.g. "query" or "sql"
    name: Optional[str] = None
    # The path to the parameter, e.g. "['outputs']['query']"
    path: str
    # The type of the parameter, e.g. "string" or "number"
    type: Optional[str] = None


class Mapping(BaseModel):
    # The source endpoint (output parameter of AP1)
    source: MappingEndpoint
    # The destination endpoint (input parameter of AP2)
    destination: MappingEndpoint
    # The confidence of the mapping, between 0 and 1
    confidence: Optional[float] = None
    # An optional reason for the mapping, e.g. "Both fields represent an SQL query."
    reason: Optional[str] = None

    def normalize(self) -> tuple:
        def _norm_path(p: str) -> str:
            return p.replace('"', "'")
        return (self.source.node_id, _norm_path(self.source.path), self.destination.node_id, _norm_path(self.destination.path))

    def __eq__(self, value):
        if not isinstance(value, Mapping):
            return False
        return self.normalize() == value.normalize()
