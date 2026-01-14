
from logging import getLogger
from typing import List

from pydantic import ValidationError

from ap_management.domain import AnalyticalPattern, CrudFailure, PgJson
from ap_management.repository import ApRepository, RepositoryError

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
            raise CrudFailure(
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
            raise CrudFailure(
                "Could not retrieve analytical pattern"
            ) from e

    def validate(self, candidate: PgJson) -> List[str]:
        """
        Ensures a PG-JSON model is a valid analytical pattern.
        Returns the list of errors encountered.
        """
        errors: List[str] = []
        try:
            AnalyticalPattern.model_validate(candidate.model_dump())
        except ValidationError as ex:
            # Pydantic field / model validation errors
            errors = [e["msg"] for e in ex.errors()]
        except ValueError as ex:
            # model_validator(after) errors
            errors = [str(ex)]
        except AssertionError as ex:
            errors = [str(ex)]

        return errors
