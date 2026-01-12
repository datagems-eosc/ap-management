from logging import getLogger
from typing import Dict, LiteralString, cast

from neo4j import AsyncSession, AsyncTransaction
from neo4j.exceptions import Neo4jError

from ap_management.domain import PgJson

from .ap_repository import ApRepository, RepositoryError

logger = getLogger(__name__)

# Note : Inheritance is not mandatory with Protocols, this is just
# to make it obvious


class Neo4jApRepository(ApRepository):

    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, ap: PgJson) -> None:
        async def _tx(tx):
            await self.__create_all_nodes(tx, ap)
            await self.__create_all_edges(tx, ap)

        try:
            await self._session.execute_write(_tx)
        except Neo4jError as e:
            logger.error("Neo4j failure while creating AP", exc_info=e)
            raise RepositoryError("Failed to persist AP") from e

    def __sanitize_keys(self, props: Dict[str, str]) -> Dict[str, str]:
        """
        Remove invalid characters from labels 
        Invalid characters | Replacement 
        '-' -> '_'
        """
        if not props:
            return {}
        return {k.replace("-", "_"): v for k, v in props.items()}

    async def __create_all_edges(self, tx: AsyncTransaction, graph: PgJson) -> None:
        for edge in graph.edges:
            labels = ":".join(edge.labels)
            props = self.__sanitize_keys(edge.properties or {})

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

    async def __create_all_nodes(self, tx: AsyncTransaction, graph: PgJson) -> None:
        for node in graph.nodes:
            labels = ":".join(node.labels)
            props = self.__sanitize_keys(node.properties or {})
            props["id"] = node.id

            prop_assignments = ", ".join(f"{k}: ${k}" for k in props.keys())

            query = f"""
            MERGE (n:{labels} {{id: $id}})
            SET n += {{{prop_assignments}}}
            """

            await tx.run(cast(LiteralString, query), props)
