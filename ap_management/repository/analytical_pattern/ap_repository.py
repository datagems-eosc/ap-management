from typing import List, Protocol

from ap_management.domain import AnalyticalPattern


class ApRepository(Protocol):
    """
    Facade to store Ap.
    This decorellate AP representation from their physical storage
    """

    async def create(self, ap: AnalyticalPattern) -> None: ...

    async def get(self, id: str) -> AnalyticalPattern | None: ...

    async def get_by_task_id(self, task_id: str) -> List[str]: ...
    """Retrieve all Analytical Patterns IDS associated to a Task ID"""
