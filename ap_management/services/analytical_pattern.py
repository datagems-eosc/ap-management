
from logging import getLogger
from typing import Any, List

from pydantic import ValidationError

from ap_management.domain import AnalyticalPattern, CrudError, PgJson
from ap_management.domain.analytical_pattern_schema_registry import ApSchemaRegistry
from ap_management.domain.exceptions import SchemaNotFoundError, SchemaUnavailableError
from ap_management.repository import ApRepository, RepositoryError

logger = getLogger(__name__)


class AnalyticalPatternService:

    _repo: ApRepository
    _schema_registry_base_url: str

    def __init__(self, repo: ApRepository, schema_registry_base_url: str):
        self._repo = repo
        self._schema_registry_base_url = schema_registry_base_url

    async def create(self, ap: AnalyticalPattern) -> str:
        """
        Create a new Analytical pattern by using its schema.
        Return the Analytical Pattern node id.
        """
        try:
            await self._repo.create(ap)

            return ap.root.id
        except RepositoryError as e:
            raise CrudError(
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
            raise CrudError(
                "Could not retrieve analytical pattern"
            ) from e

    async def validate(self, schema_uri: str, candidate: PgJson) -> List[Any]:
        """
        Ensures a PG-JSON model is a valid analytical pattern.
        Returns the list of errors encountered.
        """
        errors: List[Any] = []
        try:
            # Validate PG-JSON shape with the Pydantic model first.
            ap = AnalyticalPattern.model_validate(candidate.model_dump())
            registry = ApSchemaRegistry(self._schema_registry_base_url)
            errors = await registry.validate(ap, schema_uri)
            return errors
        except SchemaNotFoundError as ex:
            # Schema does not exist (404)
            logger.error(f"Schema not found: {ex}")
            raise
        except SchemaUnavailableError as ex:
            # Schema service unavailable (5xx or connection error)
            logger.error(f"Schema service unavailable: {ex}")
            raise
        except ValidationError as ex:
            # Pydantic field / model validation errors
            errors = [e["msg"] for e in ex.errors()]
        except ValueError as ex:
            # model_validator(after) errors
            errors = [str(ex)]
        except AssertionError as ex:
            errors = [str(ex)]

        return errors
