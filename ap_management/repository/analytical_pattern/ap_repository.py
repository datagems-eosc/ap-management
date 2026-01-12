from typing import Protocol

from domain.pg_json import PgJson


class ApRepository(Protocol):
    """
    Facade to store Ap.
    This decorellate AP representation from their physical storage
    """

    async def create(self, ap: PgJson) -> None: ...


class RepositoryError(Exception):
    ...
