from logging import getLogger
from typing import List

from fastapi import Depends, HTTPException, Path, status

from ap_management.di import get_task_service
from ap_management.domain import CrudError, NotFoundError
from ap_management.services.task import TaskService

logger = getLogger(__name__)


async def retrieve_aps(id: str = Path(..., description="The Task UUID to look for"), svc: TaskService = Depends(get_task_service)) -> List[str]:
    """
    Returns all Analytical Pattern associated to the given Task ID.
    """
    try:
        return await svc.retrieve_aps_ids(task_id=id)

    except NotFoundError as e:
        logger.warning(str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CrudError as e:
        logger.error("Database connection failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve the AP (Database error)"
        ) from e
