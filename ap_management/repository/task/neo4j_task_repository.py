from logging import getLogger

from neo4j import AsyncSession
from neo4j.exceptions import Neo4jError

from ap_management.domain import PgJsonNode
from ap_management.repository.neo4j_pgson_mixin import Neo4jPgJsonMixin

from .task_repository import TaskRepository

logger = getLogger(__name__)


class Neo4jTaskRepository(Neo4jPgJsonMixin, TaskRepository):

    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, task: PgJsonNode) -> PgJsonNode:
        """
        Store a PgJsonNode task in Neo4j.
        """

        async def _tx(tx):
            await self.create_pgson_node(tx, task)

        try:
            await self._session.execute_write(_tx)
            return task
        except Neo4jError as e:
            logger.error("Neo4j failure while creating task", exc_info=e)
            raise

    async def get(self, id: str) -> PgJsonNode | None:
        raise NotImplementedError("Method not implemented yet")
