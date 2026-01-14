from logging import getLogger
from typing import List
from uuid import uuid4

from ap_management.domain import CrudError, NotFoundError, PgJsonNode
from ap_management.repository import ApRepository, RepositoryError, TaskRepository

logger = getLogger(__name__)


class TaskService:

    _task_repo: TaskRepository
    _ap_repo: ApRepository

    def __init__(self, task_repo: TaskRepository, ap_repo: ApRepository):
        self._task_repo = task_repo
        self._ap_repo = ap_repo

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

            return await self._task_repo.create(task=task)
        except RepositoryError as e:
            logger.error("Failed to create task", exc_info=e)
            raise CrudError("Failed to create task") from e

    async def retrieve_aps_ids(self, task_id: str) -> List[str]:
        """
        Retrieve all Analytical Patterns IDS associated to a Task ID
        """
        try:
            task = await self._task_repo.get(id=task_id)
            if task is None:
                raise NotFoundError("Task not found")

            return await self._ap_repo.get_by_task_id(task_id=task_id)
        except RepositoryError as e:
            logger.error(
                "Failed to retrieve Analytical Patterns for task", exc_info=e)
            raise CrudError("Failed to retrieve Analytical Patterns") from e
