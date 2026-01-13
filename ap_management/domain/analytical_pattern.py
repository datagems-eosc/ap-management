from graphlib import CycleError
from typing import Self, cast

from deepdiff import DeepDiff
from pydantic import model_validator

from .pg_json import PgJson, PgJsonNode


class AnalyticalPattern(PgJson):

    _root: PgJsonNode

    @model_validator(mode="after")
    def check_root_node(self: Self) -> Self:
        ROOT_LABEL = "Analytical_Pattern"

        # Basic check
        ap_nodes = [n for n in self.nodes if ROOT_LABEL in n.labels]
        if not ap_nodes:
            raise ValueError(f"No '{ROOT_LABEL}' nodes found")

        if len(ap_nodes) > 1:
            root_ids = ", ".join(n.id for n in ap_nodes)
            raise ValueError(
                f"Multi-root AP detected (root nodes ids: {root_ids})"
            )

        root = ap_nodes[0]

        if not root.id:
            raise ValueError(f"The root '{ROOT_LABEL}' node has no id!")

        self._root = root

        # Ensure the undirected graph is properly connected to the root
        # i.e : "Ensure all nodes are reachable from the root, no matter the direction"
        reachable = set(self._dfs_iter_undirected(self.root.id))
        all_ids = {n.id for n in self.nodes}

        if reachable != all_ids:
            unreachable = ", ".join(sorted(all_ids - reachable))
            raise ValueError(
                f"Graph is not fully connected. "
                f"Unreachable nodes from root: {unreachable}"
            )

        # Ensure there are no cycle even if we follow the directions
        # TODO: To clarify, do we need this ?
        try:
            _ = list(self.topological_iterator())
        except CycleError as e:
            raise ValueError(f"The graph has a cycle! {e}") from e

        return self

    @property
    def root(self) -> PgJsonNode:
        """Return the AP root node"""
        return self._root

    def normalize(self) -> Self:
        """
        Normalize the AP in place:
        - Sorts nodes by id
        - Sorts edges by from_, to, labels
        - Sorts labels alphabetically
        """
        for n in self.nodes:
            if getattr(n, "labels", None):
                n.labels = sorted(n.labels)
        self.nodes.sort(key=lambda n: n.id)

        for e in self.edges:
            if getattr(e, "labels", None):
                e.labels = sorted(e.labels)
        self.edges.sort(key=lambda e: (e.from_, e.to, tuple(e.labels)))
        return self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AnalyticalPattern):
            return NotImplemented

        # Simple assertions before doing the expensive computation
        assert other is not None
        assert len(other.nodes) == len(other.nodes)
        assert len(other.edges) == len(other.edges)

        # NOTE : Casting to Self is not necessary but it prevent a warning
        # as Pylance doesn't recognize the pseudo class "Self" as the same as
        # the complete class "Analytical pattern"
        # So this is safe to do
        return self.difference(cast(Self, other)) == {}

    def difference(self, other: Self) -> DeepDiff:
        return DeepDiff(self.normalize(), other.normalize(), ignore_order=True)
