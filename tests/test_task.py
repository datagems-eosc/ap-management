import pytest

from ap_management.domain import PgJsonNode
from ap_management.services.task import TaskService


@pytest.mark.asyncio
async def test_create_task(task_svc: TaskService):
    """
    Test creating a simple task
    """
    request = "Test task description"
    name = "Test Task"
    task = await task_svc.create(name=name, request=request)

    assert isinstance(task, PgJsonNode)
    assert task.id is not None
    assert "Task" in task.labels
    assert task.properties is not None
    assert task.properties["Description"] == request
