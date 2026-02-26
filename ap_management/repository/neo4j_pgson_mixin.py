from logging import getLogger
from typing import Dict, List, LiteralString, Optional, cast

from neo4j import AsyncTransaction, Record

from ap_management.domain import PgJson, PgJsonEdge, PgJsonNode

logger = getLogger(__name__)


class Neo4jPgJsonMixin:
    """
    Mixin class providing common Neo4j operations for PJson nodes and edges.

    This mixin provides methods to:
    - Store individual PJson nodes and edges in Neo4j
    - Retrieve PJson structures from Neo4j
    - Handle property sanitization and label escaping
    """

    @staticmethod
    def _sanitize_properties(props: Optional[Dict[str, str]]) -> Dict[str, str]:
        """
        Remove invalid characters from properties keys.

        Invalid characters | Replacement
        '-' -> '_'

        Args:
            props: Dictionary of properties to sanitize

        Returns:
            Sanitized properties dictionary
        """
        if not props:
            return {}
        return {k.replace("-", "_"): v for k, v in props.items()}

    @staticmethod
    def _escape_labels(labels: List[str]) -> List[str]:
        """
        Wrap labels in backticks. This allows separators like ":" to appear in labels.

        Args:
            labels: List of label strings

        Returns:
            List of escaped labels
        """
        return [f"`{label}`" for label in labels]

    async def create_pgson_node(
        self, tx: AsyncTransaction, node: PgJsonNode
    ) -> None:
        """
        Store a single PJson node in Neo4j.

        Creates or updates a node with the given id, labels, and properties.

        Args:
            tx: Neo4j async transaction
            node: PJsonNode to store

        Raises:
            Exception: If Neo4j operation fails
        """
        labels = ":".join(self._escape_labels(node.labels))
        props = self._sanitize_properties(node.properties or {})
        props["id"] = node.id

        prop_assignments = ", ".join(f"{k}: ${k}" for k in props.keys())

        query = f"""
        MERGE (n:{labels} {{id: $id}})
        SET n += {{{prop_assignments}}}
        """

        await tx.run(cast(LiteralString, query), props)

    async def create_pgson_edge(
        self, tx: AsyncTransaction, edge: PgJsonEdge
    ) -> None:
        """
        Store a single PJson edge in Neo4j.

        Creates or updates an edge between two nodes with given labels and properties.
        WARNING : This Assumes both nodes already exist in the database.

        Args:
            tx: Neo4j async transaction
            edge: PJsonEdge to store

        Raises:
            Exception: If Neo4j operation fails
        """
        labels = ":".join(self._escape_labels(edge.labels))
        props = self._sanitize_properties(edge.properties or {})

        query = f"""
        MATCH (a {{id: $from_id}})
        MATCH (b {{id: $to_id}})
        MERGE (a)-[r:{labels}]->(b)
        """

        if props:
            prop_assignments = ", ".join(f"{k}: ${k}" for k in props.keys())
            query += f"\nSET r += {{{prop_assignments}}}"

        parameters = {
            "from_id": edge.from_,
            "to_id": edge.to,
            **props,
        }

        await tx.run(cast(LiteralString, query), parameters)

    async def create_pgson(
        self, tx: AsyncTransaction, pg_json: PgJson
    ) -> None:
        """
        Store an entire PJson structure (nodes and edges) in Neo4j.

        Creates all nodes first, then creates all edges between them.

        Args:
            tx: Neo4j async transaction
            pg_json: PgJson structure to store

        Raises:
            Exception: If Neo4j operation fails
        """
        for node in pg_json.nodes:
            await self.create_pgson_node(tx, node)

        for edge in pg_json.edges:
            await self.create_pgson_edge(tx, edge)

    @staticmethod
    def _records_to_pgson(record: Record) -> PgJson:
        """
        Convert a Neo4j query result record into a PgJson structure.

        Expected record format:
        - record["nodes"]: List of Neo4j Node objects
        - record["edges"]: List of Neo4j Relationship objects

        Args:
            record: Neo4j Record containing nodes and edges

        Returns:
            PgJson object

        Raises:
            ValidationError: If conversion fails
        """
        pg_nodes = [
            PgJsonNode(
                **{
                    "id": n._properties["id"],
                    "labels": list(n.labels),
                    # NOTE: the "id" is its own property, it can be removed from there
                    # NOTE: "description_embedding" is an internal vector field, not part of the domain model
                    "properties": {
                        k: v for k, v in n._properties.items() if k not in {"id", "description_embedding"}
                    },
                }
            )
            for n in record["nodes"]
        ]

        pg_edges = [
            PgJsonEdge(
                **{
                    "from": e.start_node._properties["id"],
                    "to": e.end_node._properties["id"],
                    "labels": [e.type] if isinstance(e.type, str) else list(e.type),
                    "properties": dict(e._properties),
                }
            )
            for e in record["edges"]
        ]

        return PgJson.model_validate({"nodes": pg_nodes, "edges": pg_edges})
