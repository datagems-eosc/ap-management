from uuid import uuid4

import pytest

from ap_management.domain import AnalyticalPattern, PgJsonEdge, PgJsonNode
from ap_management.services.analytical_pattern import AnalyticalPatternService
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


@pytest.mark.asyncio
async def test_task_with_aps(task_svc: TaskService, ap_svc: AnalyticalPatternService):
    """
    Test creating a task, attaching two minimal APs to it,
    and verifying get_aps_by_task_id retrieves both APs.
    """
    # Create a task
    task = await task_svc.create(name="Task with APs", request="Test task with APs")
    task_id = task.id

    # Create two minimal APs connected to the task
    ap_ids = []
    for i in range(2):
        ap_root_id = str(uuid4())
        root_node = PgJsonNode.model_validate({
            "id": ap_root_id,
            "labels": ["Analytical_Pattern"],
            "properties": {"Name": f"Test AP {i+1}"}
        })
        # NOTE: using model_construct to skip validation
        # As this graph is willingly not correctly connected
        ap = AnalyticalPattern.model_construct(
            nodes=[
                root_node
            ],
            edges=[
                PgJsonEdge.model_validate({
                    "from": task_id,
                    "to": ap_root_id,
                    "labels": ["is_achieved"],
                    "properties": {}
                })
            ],
            # Setting this manually as validation will not run
            _root=root_node
        )
        ap_id = await ap_svc.create(ap)
        ap_ids.append(ap_id)

    # Test retrieving APs by task ID
    retrieved_ap_ids = await task_svc.retrieve_aps_ids(task_id)

    assert len(retrieved_ap_ids) == 2
    assert set(retrieved_ap_ids) == set(ap_ids)
