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
                // Get the root Analytical_Pattern by id 
                MATCH (root:Analytical_Pattern {id: $id})
                // Find all operators that are part of this AP (consist_of relationship)
                MATCH (root)-[:consist_of]->(operator:Operator)
                // Find all data and models connected to these operators
                OPTIONAL MATCH (operator)-[rel1:input|output|perform]->(data)
                OPTIONAL MATCH (data)-[rel2:input|output|perform]->(operator)
                // Collect all nodes: root, operators, and connected data/models
                WITH 
                    root, 
                    collect(DISTINCT operator) AS operators,
                    collect(DISTINCT data) AS dataNodes
                // Collect all nodes together
                WITH [root] + operators + dataNodes AS allNodes
                // Collect all relationships between these nodes
                UNWIND allNodes AS node1
                OPTIONAL MATCH (node1)-[rel]->(node2)
                WHERE node2 IN allNodes
                WITH allNodes, collect(DISTINCT rel) AS edges
                RETURN allNodes AS nodes, edges
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
