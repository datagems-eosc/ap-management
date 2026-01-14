from logging import getLogger
from uuid import uuid4

from ap_management.domain import CrudFailure, PgJsonNode
from ap_management.repository import RepositoryError, TaskRepository

logger = getLogger(__name__)


class TaskService:

    _repo: TaskRepository

    def __init__(self, repo: TaskRepository):
        self._repo = repo

    async def create(self, name: str, request: str) -> PgJsonNode:

        try:

            id = str(uuid4())

            properties = {
                "Name": name,
                "Description": request
            }

            task = PgJsonNode(
                id=id,
                labels=["Task"],
                properties=properties
            )

            return await self._repo.create(task=task)
        except RepositoryError as e:
            logger.error("Failed to create task", exc_info=e)
            raise CrudFailure("Failed to create task") from e
