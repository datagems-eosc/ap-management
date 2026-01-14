from logging import getLogger
from typing import Any, Dict, List

from neo4j import AsyncManagedTransaction, AsyncSession, Record
from neo4j.exceptions import Neo4jError
from pydantic import ValidationError

from ap_management.domain import AnalyticalPattern
from ap_management.repository.analytical_pattern.ap_repository import ApRepository
from ap_management.repository.neo4j_pgson_mixin import Neo4jPgJsonMixin
from ap_management.repository.repository_error import RepositoryError

logger = getLogger(__name__)


class Neo4jApRepository(Neo4jPgJsonMixin, ApRepository):

    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, ap: AnalyticalPattern) -> None:
        async def _tx(tx):
            await self.create_pgson(tx, ap)

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
            pg_json = self._records_to_pgson(record)

            return AnalyticalPattern.model_validate(pg_json.model_dump())

        except (Neo4jError, ValidationError) as e:
            logger.error("Neo4j failure while retrieving AP", exc_info=e)
            raise RepositoryError("Failed to retrieve AP") from e

    async def get_by_task_id(self, task_id: str) -> List[str]:
        async def _tx(tx: AsyncManagedTransaction) -> List[Dict[str, Any]]:
            # TODO Check cypher query
            result = await tx.run(
                """//cypher
                // Get all Analytical Pattern nodes linked to the Task ID
                MATCH (t:Task {id: $task_id})-[:is_achieved]->(ap:Analytical_Pattern)
                RETURN ap.id AS ap_id
                """,
                {"task_id": task_id},
            )
            return await result.data()

        try:
            records = await self._session.execute_read(_tx)
            ap_ids = [record["ap_id"] for record in records]
            return ap_ids

        except Neo4jError as e:
            logger.error(
                "Neo4j failure while retrieving APs by Task ID", exc_info=e)
            raise RepositoryError("Failed to retrieve APs by Task ID") from e
