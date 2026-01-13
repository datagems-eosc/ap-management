from typing import Self, cast

from deepdiff import DeepDiff
from pydantic import model_validator

from .pg_json import PgJson, PgJsonNode


class AnalyticalPattern(PgJson):

    _root: PgJsonNode

    @model_validator(mode="after")
    def check_root_node(self: Self) -> Self:
        """
        Validate that the AP has a root node.
        The root node have the following properties :
        - Its label must contain "Analytical_Pattern"
        - No edges must lead to it 

        Beware : AP can be nested, so multiple "Analytical_Pattern" nodes can exists
        """
        # Find all the Analytical_Pattern nodes
        ROOT_LABEL = "Analytical_Pattern"
        ap_nodes = [n for n in self.nodes if ROOT_LABEL in n.labels]
        if not ap_nodes:
            raise ValueError(f"No '{ROOT_LABEL}' nodes found")

        # Ensure there is only one root
        match len(ap_nodes):
            case 0:
                raise ValueError(
                    f"No root '{ROOT_LABEL}' node found (must have no incoming edges)"
                )
            case n if n > 1:
                root_ids = ', '.join([n.id for n in ap_nodes])
                raise ValueError(
                    f"Multi-root AP detected (root nodes ids: {root_ids})"
                )

        # Ensure the root has an id
        # TODO: Should the id be generated if not found ?
        if not ap_nodes[0].id:
            raise ValueError("The root '{ROOT_LABEL}' node has no id !")

        self._root = ap_nodes[0]
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
