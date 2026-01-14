from collections import defaultdict
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field


class PgJsonNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    labels: List[str]
    properties: Optional[Dict[str, Any]] = {}


class PgJsonEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from")
    labels: List[str]
    to: str
    properties: Optional[Dict[str, Any]] = {}

    @property
    def from_id(self) -> str:
        """Backward compatibility property"""
        return self.from_


class PgJson(BaseModel):
    nodes: List[PgJsonNode]
    edges: List[PgJsonEdge]

    def get_node_by_id(self, node_id: str) -> Optional[PgJsonNode]:
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_edges_from(self, node_id: str) -> List[PgJsonEdge]:
        return [e for e in self.edges if e.from_ == node_id]

    def get_edges_to(self, node_id: str) -> List[PgJsonEdge]:
        return [e for e in self.edges if e.to == node_id]

    def get_nodes_by_label(self, label: str) -> List[PgJsonNode]:
        return [n for n in self.nodes if label in n.labels]

    def _dfs_iter(self, start_id: str) -> Iterator[str]:
        """
        Return a Depth First Search Iterator on nodes IDs
        """
        visited: Set[str] = set()
        stack = [start_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            yield current

            stack.extend(e.to for e in self.get_edges_from(current))

    def _dfs_iter_undirected(self, start_id: str) -> Iterator[str]:
        """
        Iterative DFS for undirected graphs starting from `start_id`.
        Yields all node IDs reachable from start.
        """
        visited: Set[str] = set()
        stack: list[Tuple[str, str | None]] = [
            (start_id, None)]  # (node, parent)

        # Build undirected adjacency list
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            adj[edge.from_].append(edge.to)
            adj[edge.to].append(edge.from_)

        while stack:
            node, parent = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            yield node

            for neighbor in adj[node]:
                if neighbor != parent:
                    stack.append((neighbor, node))
