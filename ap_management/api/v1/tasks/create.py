from logging import getLogger

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from ap_management.di import get_task_service
from ap_management.domain import CrudError
from ap_management.services.task import TaskService

logger = getLogger(__name__)


class CreateTaskInput(BaseModel):
    # Name of the Task
    name: str
    # What the user want to do in plain english
    request: str


class CreatePayload(BaseModel):
    id: str


async def create_task(input: CreateTaskInput, svc: TaskService = Depends(get_task_service)) -> CreatePayload:
    """
    Registers a new Task
    """
    try:
        task = await svc.create(
            name=input.name,
            request=input.request
        )
        return CreatePayload(id=task.id)

    except CrudError as e:
        logger.error("Database connection failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the Task"
        ) from e
