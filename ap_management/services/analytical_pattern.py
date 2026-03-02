
from concurrent.futures import wait
from logging import getLogger
from typing import Any, List, Optional

from pydantic import ValidationError
from table_reclamation import AccessPlanner

from ap_management.domain import AnalyticalPattern, CrudError, PgJson
from ap_management.domain.analytical_pattern_schema_registry import ApSchemaRegistry
from ap_management.domain.exceptions import SchemaNotFoundError, SchemaUnavailableError
from ap_management.repository import ApRepository, RepositoryError
from ap_management.services.analytical_pattern_generator import (
    AnalyticalPatternGenerator,
)
from ap_management.services.embeddings import Embedder

logger = getLogger(__name__)


class AnalyticalPatternService:

    _repo: ApRepository
    _schema_registry_base_url: str
    _embedder: Optional[Embedder]

    def __init__(
            self,
            repo: ApRepository,
            schema_registry_base_url: str,
            generator: AnalyticalPatternGenerator,
            embedder: Optional[Embedder] = None
    ):
        self._repo = repo
        self._schema_registry_base_url = schema_registry_base_url
        self._generator = generator
        self._embedder = embedder

    async def create(self, ap: AnalyticalPattern) -> str:
        """
        Create a new Analytical pattern by using its schema.
        Return the Analytical Pattern node id.
        """

        embedding: Optional[List[float]] = None
        if self._embedder is not None:
            description = (ap.root.properties or {}).get("description", "")
            if description:
                try:
                    embedding = await self._embedder.embed(description)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Embedding generation failed – storing AP without vector.",
                        exc_info=e,
                    )

        try:
            await self._repo.create(ap, embedding)
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

    async def search(self, q: str, top_k: int = 10) -> List[tuple[AnalyticalPattern, float]]:
        """
        Search for Analytical Patterns whose description is semantically similar
        to the given query string.

        Raises ``CrudError`` if no embedder is configured.
        Returns a list of up to ``top_k`` (AnalyticalPattern, score) tuples.
        """
        if self._embedder is None:
            raise CrudError(
                "Vector search is not available: no Embedder is configured."
            )

        try:
            query_vector = await self._embedder.embed(q)
        except Exception as e:  # noqa: BLE001
            raise CrudError("Embedding generation failed") from e

        try:
            return await self._repo.search(query_vector, top_k=top_k)
        except RepositoryError as e:
            raise CrudError(
                "Could not search analytical patterns"
            ) from e

    async def resolve(
        self, query: str, threshold: float = 0.85, top_k: int = 5
    ) -> tuple[AnalyticalPattern, float | None, bool]:
        """
        Find an existing AP semantically close to ``query`` (score >= threshold),
        or generate and persist a new one.

        Returns a ``(ap, score, created)`` tuple where ``created`` is True when
        a new AP was generated.
        """
        # Search for existing APs matching the query.
        aps = await self.search(query, top_k=top_k)
        for ap, score in aps:
            if score >= threshold:
                return ap, score, False

        try:
            new_ap = self._generator.generate(query)
            await self.create(new_ap)
            return new_ap, 1.0, True
        except ValueError as e:
            raise CrudError(
                "No Analytical Pattern generated can be generated for query. Is this query valid ?") from e
        except RepositoryError as e:
            raise CrudError(
                "Failed to persist generated Analytical Pattern") from e

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
