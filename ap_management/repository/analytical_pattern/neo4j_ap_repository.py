from logging import getLogger
from typing import Dict, List, LiteralString, cast

from neo4j import AsyncManagedTransaction, AsyncSession, AsyncTransaction, Record
from neo4j.exceptions import Neo4jError
from pydantic import ValidationError

from ap_management.domain import AnalyticalPattern, PgJsonEdge, PgJsonNode

from .ap_repository import ApRepository, RepositoryError

logger = getLogger(__name__)

# Note : Inheritance is not mandatory with Protocols, this is just
# to make it obvious


class Neo4jApRepository(ApRepository):

    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, ap: AnalyticalPattern) -> None:
        async def _tx(tx):
            await self.__create_all_nodes(tx, ap)
            await self.__create_all_edges(tx, ap)

        try:
            await self._session.execute_write(_tx)
        except Neo4jError as e:
            logger.error("Neo4j failure while creating AP", exc_info=e)
            raise RepositoryError("Failed to persist AP") from e

    async def get(self, id: str) -> AnalyticalPattern | None:
        async def _tx(tx: AsyncManagedTransaction) -> Record | None:
            result = await tx.run(
                """//cypher
                // Get the root by id 
                MATCH (root:Analytical_Pattern {id: $id})
                // Find all children and ancestors with a distance >=1
                MATCH p = (root)-[*1..]-(n)
                // Gather everything with a list of nodes and a list of relationship per node
                // so relLists = [relationships(node_1), .., relationships(node_n)]
                //             = [ [node_1_rel_1, ... node_1_rel_n], ..., [node_n_rel_1, ... node_n_rel_n]]
                WITH
                    collect(DISTINCT n) AS allNodes,
                    collect(DISTINCT relationships(p)) AS relLists
                // UNDWIND is a glorified foreach, so for each list of relationship is the list of list
                UNWIND relLists AS relList
                // And for each relationship in each relationship list
                UNWIND relList AS rel
                // Flatten and dedup
                RETURN
                    allNodes AS nodes,
                    collect(DISTINCT rel) AS edges
                """,
                {"id": id},
            )
            return await result.single()

        try:
            record = await self._session.execute_read(_tx)
            if record is None:
                return None

            # Convert root + nodes + edges into PgJson
            pg_nodes = [
                PgJsonNode(
                    **{"id": n._properties['id'],
                       "labels": list(n.labels),
                       # NOTE : the "id" is its own property, it can be removed from there
                       "properties": {k: v for k, v in n._properties.items() if k != 'id'}
                       })
                for n in record["nodes"]
            ]

            pg_edges = [
                PgJsonEdge(
                    **{
                        "from": e.start_node._properties['id'],
                        "to": e.end_node._properties['id'],
                        "labels": [e.type] if isinstance(e.type, str) else list(e.type),
                        "properties": dict(e._properties)
                    }
                )
                for e in record["edges"]

            ]

            return AnalyticalPattern.model_validate({"nodes": pg_nodes, "edges": pg_edges})

        except (Neo4jError, ValidationError) as e:
            logger.error("Neo4j failure while retrieving AP", exc_info=e)
            raise RepositoryError("Failed to retrieve AP") from e

    def __sanitize_properties(self, props: Dict[str, str]) -> Dict[str, str]:
        """
        Remove invalid characters from properties keys
        Invalid characters | Replacement
        '-' -> '_'
        """
        if not props:
            return {}
        return {k.replace("-", "_"): v for k, v in props.items()}

    def __escape_labels(self, labels: List[str]) -> List[str]:
        """
        Wrap labels in backticks. This allows separators like ":" to appear in labels 
        """
        return [f"`{label}`" for label in labels]

    async def __create_all_edges(self, tx: AsyncTransaction, graph: AnalyticalPattern) -> None:
        for edge in graph.edges:
            labels = ":".join(self.__escape_labels(edge.labels))
            props = self.__sanitize_properties(edge.properties or {})

            query = f"""
            MATCH (a {{id: $from_id}})
            MATCH (b {{id: $to_id}})
            MERGE (a)-[r:{labels}]->(b)
            """

            if props:
                prop_assignments = ", ".join(
                    f"{k}: ${k}" for k in props.keys())
                query += f"\nSET r += {{{prop_assignments}}}"

            parameters = {
                "from_id": edge.from_,
                "to_id": edge.to,
                **props,
            }

            await tx.run(cast(LiteralString, query), parameters)

    async def __create_all_nodes(self, tx: AsyncTransaction, graph: AnalyticalPattern) -> None:
        for node in graph.nodes:
            labels = ":".join(self.__escape_labels(node.labels))
            props = self.__sanitize_properties(node.properties or {})
            props["id"] = node.id

            prop_assignments = ", ".join(f"{k}: ${k}" for k in props.keys())

            query = f"""
            MERGE (n:{labels} {{id: $id}})
            SET n += {{{prop_assignments}}}
            """

            await tx.run(cast(LiteralString, query), props)
