from typing import Protocol

from ap_management.domain import AnalyticalPattern


class ApRepository(Protocol):
    """
    Facade to store Ap.
    This decorellate AP representation from their physical storage
    """

    async def create(self, ap: AnalyticalPattern) -> None: ...

    async def get(self, id: str) -> AnalyticalPattern | None: ...
