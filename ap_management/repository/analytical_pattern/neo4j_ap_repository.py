from logging import getLogger
from typing import Any, Dict, Final, List, LiteralString, Optional, cast

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
    _VECTOR_INDEX_NAME: Final[str] = "ap_description_embedding"

    def __init__(self, session: AsyncSession):
        self._session = session

    async def enable_embeddings(self, dimensions: int) -> None:
        """
        Create the vector index on ``Analytical_Pattern.description_embedding``
        if it does not already exist.

        Args:
            dimensions: Number of dimensions of the embedding vectors.
        """
        async def _tx(tx: AsyncManagedTransaction) -> None:
            await tx.run(
                cast(
                    LiteralString,
                    f"""//cypher
                    CREATE VECTOR INDEX `{self._VECTOR_INDEX_NAME}` IF NOT EXISTS
                    FOR (n:Analytical_Pattern) ON (n.description_embedding)
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {dimensions},
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                """,
                )
            )

        try:
            await self._session.execute_write(_tx)
            logger.info(
                "Vector index '%s' is ready (%d dims).", self._VECTOR_INDEX_NAME, dimensions
            )
        except Neo4jError as e:
            logger.error("Failed to create vector index", exc_info=e)
            raise RepositoryError("Failed to create vector index") from e

    async def create(self, ap: AnalyticalPattern, embedding: Optional[List[float]] = None) -> None:
        async def _tx(tx) -> None:
            await self.create_pgson(tx, ap)
            if embedding is not None:
                await tx.run(
                    """//cypher
                    MATCH (n:Analytical_Pattern {id: $id})
                    CALL db.create.setNodeVectorProperty(n, 'description_embedding', $embedding)
                    """,
                    {"id": ap.root.id, "embedding": embedding},
                )

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

    async def search(self, query_vector: List[float], top_k: int = 10) -> List[tuple[AnalyticalPattern, float]]:
        """
        Search Analytical Patterns by cosine similarity against a pre-computed query vector.

        Args:
            query_vector: The embedding of the natural language query, produced by the service layer.
            top_k:        Maximum number of results to return (default 10).
        """
        async def _tx_list(tx: AsyncManagedTransaction) -> List[Record]:
            result = await tx.run(
                """//cypher
                // Approximate nearest-neighbour search on the vector index
                CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector)
                YIELD node AS root, score
                // Retrieve the full graph for each matched root
                MATCH (root)-[:consist_of]->(operator:Operator)
                OPTIONAL MATCH (operator)-[:input|output|perform]->(data)
                OPTIONAL MATCH (data)-[:input|output|perform]->(operator)
                WITH
                    root,
                    score,
                    collect(DISTINCT operator) AS operators,
                    collect(DISTINCT data) AS dataNodes
                WITH root, score, [root] + operators + dataNodes AS allNodes
                UNWIND allNodes AS node1
                OPTIONAL MATCH (node1)-[rel]->(node2)
                WHERE node2 IN allNodes
                WITH root, score, allNodes, collect(DISTINCT rel) AS edges
                RETURN allNodes AS nodes, edges, score
                """,
                {
                    "index_name": self._VECTOR_INDEX_NAME,
                    "top_k": top_k,
                    "query_vector": query_vector,
                },
            )
            return [record async for record in result]

        try:
            records = await self._session.execute_read(_tx_list)
            results: List[tuple[AnalyticalPattern, float]] = []
            for record in records:
                pg_json = self._records_to_pgson(record)
                ap = AnalyticalPattern.model_validate(pg_json.model_dump())
                results.append((ap, record["score"]))
            return results

        except (Neo4jError, ValidationError) as e:
            logger.error("Neo4j failure while searching APs", exc_info=e)
            raise RepositoryError(
                "Failed to search analytical patterns") from e
