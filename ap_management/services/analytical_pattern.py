
from logging import getLogger

from ap_management.domain import AnalyticalPattern, ApCRUDFailure
from ap_management.repository.analytical_pattern import ApRepository, RepositoryError

logger = getLogger(__name__)


class AnalyticalPatternService:

    _repo: ApRepository

    def __init__(self, repo: ApRepository):
        self._repo = repo

    async def create(self, ap: AnalyticalPattern) -> str:
        """
        Create a new Analytical pattern by using its schema.
        Return the Analytical Pattern node id.
        """
        try:
            await self._repo.create(ap)

            return ap.root.id
        except RepositoryError as e:
            raise ApCRUDFailure(
                "Could not create analytical pattern"
            ) from e

    async def get(self, id: str) -> AnalyticalPattern | None:
        """
        Retrieve an Analytical Pattern using its id.

        Return either the analytical Pattern or None if not found

        """
        try:
            return await self._repo.get(id)
        except RepositoryError as e:
            raise ApCRUDFailure(
                "Could not retrieve analytical pattern"
            ) from e
