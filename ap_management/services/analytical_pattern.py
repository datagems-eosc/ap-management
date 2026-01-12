
from logging import getLogger

from ap_management.domain import AnalyticalPattern, ApCreationFailed
from ap_management.repository.analytical_pattern import ApRepository, RepositoryError

logger = getLogger(__name__)


class AnalyticalPatternService:

    _repo: ApRepository

    def __init__(self, repo: ApRepository):
        self._repo = repo

    async def create(self, ap: AnalyticalPattern) -> str:
        try:
            await self._repo.create(ap)

            return ap.root.id
        except RepositoryError as e:
            raise ApCreationFailed(
                "Could not create analytical pattern"
            ) from e
