from typing import Protocol

from ap_management.domain import PgJsonNode


class TaskRepository(Protocol):
    """
    Facade to store Tasks.
    This decorellate Tasks representation from their physical storage
    """

    async def create(self, task: PgJsonNode) -> PgJsonNode: ...

    async def get(self, id: str) -> PgJsonNode | None: ...
