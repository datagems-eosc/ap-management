from typing import Any, List
from urllib.parse import urljoin

from httpx import HTTPStatusError, RequestError, get
from jsonschema import Draft7Validator, ValidationError
from pydantic import BaseModel
from referencing import Registry, Resource

from .analytical_pattern import AnalyticalPattern
from .exceptions import SchemaNotFoundError, SchemaUnavailableError


class ApSchemaError(BaseModel):
    keyword: str
    instancePath: str
    schemaPath: str
    params: dict[str, Any]
    message: str


class ApSchemaRegistry:

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.registry = Registry(retrieve=self._fetch_resource)
        self.edge_relationship_rules: dict[str, dict] = {}

    async def _ingest_schema(self, uri: str):
        if uri.startswith("http://") or uri.startswith("https://"):
            raise ValueError(
                "Full URLs are not supported. Provide a relative URI.")

        schema = self._fetch_resource(uri).contents

        rules = schema.get("x-edge-relationship-rules")
        if isinstance(rules, dict):
            self.edge_relationship_rules = {
                k: {
                    "from_": v.get("from", []),
                    "to": v.get("to", [])
                }
                for k, v in rules.items()
            }

        self.registry = self.registry.with_resource(
            uri,
            Resource.from_contents(schema)
        )
        return schema

    def _fetch_resource(self, uri: str) -> Resource[Any]:
        """
        Resolve a schema URI over HTTP(S) and return a referencing Resource.
        Raises:
            SchemaNotFoundError: If the schema does not exist (404).
            SchemaUnavailableError: If the schema service is unavailable (5xx or connection error).
        """
        full_uri = urljoin(self.base_url, uri)
        try:
            response = get(full_uri)
            response.raise_for_status()
            return Resource.from_contents(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SchemaNotFoundError(
                    f"Schema not found at {full_uri}"
                ) from e
            elif e.response.status_code >= 500:
                raise SchemaUnavailableError(
                    f"Schema service unavailable: {e.response.status_code}"
                ) from e
            else:
                raise SchemaUnavailableError(
                    f"Failed to fetch schema: {e.response.status_code}"
                ) from e
        except RequestError as e:
            raise SchemaUnavailableError(
                f"Cannot connect to schema service at {full_uri}"
            ) from e

    async def validate(self, candidate: AnalyticalPattern, schema_uri: str) -> List[ApSchemaError]:
        """
        Validate a candidate Analytical Pattern against the schema located at schema_uri.
        Return the list of AJV-like errors encountered.

        Args:
            candidate (AnalyticalPattern): The candidate Analytical Pattern to validate.
            schema_uri (str): The relative URI of the schema to validate against.
        Returns:
            List[ApSchemaError]: List of validation errors in AJV format.
        """
        schema = await self._ingest_schema(schema_uri)
        validator = Draft7Validator(schema, registry=self.registry)
        return [self.wrap_to_ajv(e) for e in validator.iter_errors(candidate.model_dump(by_alias=True))]

    def wrap_to_ajv(self, err: ValidationError) -> ApSchemaError:
        """
        Wrap any error from jsonschema to an AJV-like error.
        This is to have a consistent error format that can be easily consumed
        """
        return ApSchemaError(
            keyword=str(err.validator),
            instancePath="/" + "/".join(map(str, err.path)),
            schemaPath="#/" + "/".join(map(str, err.schema_path)),
            params=getattr(err, "params", {}),
            message=err.message
        )
