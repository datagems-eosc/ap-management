from pathlib import Path
from typing import Any, Callable, List
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
        self.edge_relationship_rules: dict[str, dict] = {}

        # Determine retrieval strategy based on base_url
        retrieve_fn: Callable[[str], Resource[Any]]
        if base_url.startswith("file://"):
            retrieve_fn = self._fetch_resource_from_file
        elif base_url.startswith(("http://", "https://")):
            retrieve_fn = self._fetch_resource_from_http
        else:
            raise ValueError(
                "Unsupported base URL scheme. Use 'file://' for local files or 'http(s)://' for HTTP resources."
            )

        self.registry = Registry(retrieve=retrieve_fn)

    async def _ingest_schema(self, uri: str):
        if uri.startswith("http://") or uri.startswith("https://"):
            raise ValueError(
                "Full URLs are not supported. Provide a relative URI.")

        schema = self.registry.get_or_retrieve(uri).value.contents

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

    def _fetch_resource_from_file(self, uri: str) -> Resource[Any]:
        """
        Resolve a schema URI from local filesystem and return a referencing Resource.
        Raises:
            SchemaNotFoundError: If the schema file is not found.
            SchemaUnavailableError: If the schema file cannot be read.
        """
        if self.base_url.startswith("file://"):
            base_path = Path(self.base_url[7:])  # Remove file:// prefix
        else:
            base_path = Path(self.base_url)

        file_path = base_path / uri.lstrip("/")

        try:
            import json
            with open(file_path, "r") as f:
                return Resource.from_contents(json.load(f))
        except FileNotFoundError:
            raise SchemaNotFoundError(
                f"Schema file not found at {file_path}"
            )
        except (OSError, IOError) as e:
            raise SchemaUnavailableError(
                f"Cannot read schema file at {file_path}: {e}"
            )

    def _fetch_resource_from_http(self, uri: str) -> Resource[Any]:
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

    def _matches_operator_rule(self, node_labels: List[str], required_labels: List[str]) -> bool:
        """
        Check if a node matches the required labels with Operator wildcard support.
        If rule requires "Operator", any node with "Operator" label or ending in "_Operator" is valid.
        """
        if "Operator" in required_labels:
            if any(label == "Operator" or label.endswith("_Operator") for label in node_labels):
                return True
        return any(required_label in node_labels for required_label in required_labels)

    def _validate_edge_relationships(self, candidate: AnalyticalPattern) -> List[ApSchemaError]:
        """
        Validate edge relationships according to x-edge-relationship-rules from the schema.
        """
        errors: List[ApSchemaError] = []

        if not self.edge_relationship_rules:
            return errors

        graph = candidate.model_dump(by_alias=True)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # Create a map of node ID to labels
        node_map = {node["id"]: node.get("labels", []) for node in nodes}

        for edge_index, edge in enumerate(edges):
            from_id = edge.get("from")
            to_id = edge.get("to")
            edge_labels = edge.get("labels", [])

            from_node_labels = node_map.get(from_id)
            to_node_labels = node_map.get(to_id)

            # Check if nodes exist
            if from_node_labels is None:
                errors.append(ApSchemaError(
                    keyword="edgeRelationship",
                    instancePath=f"/edges/{edge_index}/from",
                    schemaPath="#/x-edge-relationship-rules",
                    params={"edgeIndex": edge_index, "nodeId": from_id},
                    message=f"Edge 'from' node with ID '{from_id}' does not exist"
                ))
                continue

            if to_node_labels is None:
                errors.append(ApSchemaError(
                    keyword="edgeRelationship",
                    instancePath=f"/edges/{edge_index}/to",
                    schemaPath="#/x-edge-relationship-rules",
                    params={"edgeIndex": edge_index, "nodeId": to_id},
                    message=f"Edge 'to' node with ID '{to_id}' does not exist"
                ))
                continue

            # Validate each edge label
            for edge_label in edge_labels:
                rule = self.edge_relationship_rules.get(edge_label)

                if not rule:
                    continue

                from_valid = self._matches_operator_rule(
                    from_node_labels, rule["from_"])
                to_valid = self._matches_operator_rule(
                    to_node_labels, rule["to"])

                if not from_valid or not to_valid:
                    # Find allowed edge labels between these node types
                    allowed_labels = [
                        label for label, r in self.edge_relationship_rules.items()
                        if self._matches_operator_rule(from_node_labels, r["from_"]) and
                        self._matches_operator_rule(to_node_labels, r["to"])
                    ]

                    allowed_msg = (
                        f"Allowed relationships between these nodes: {', '.join(allowed_labels)}"
                        if allowed_labels
                        else "No valid relationships allowed between these node types"
                    )

                    errors.append(ApSchemaError(
                        keyword="edgeRelationship",
                        instancePath=f"/edges/{edge_index}/labels",
                        schemaPath=f"#/x-edge-relationship-rules/{edge_label}",
                        params={
                            "edgeIndex": edge_index,
                            "edgeLabel": edge_label,
                            "fromLabels": from_node_labels,
                            "toLabels": to_node_labels,
                            "expectedFrom": rule["from_"],
                            "expectedTo": rule["to"]
                        },
                        message=f"Invalid relationship between node of type [{', '.join(from_node_labels)}] "
                        f"and node of type [{', '.join(to_node_labels)}] with label '{edge_label}'. {allowed_msg}"
                    ))

        return errors

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
        errors = [self.wrap_to_ajv(e) for e in validator.iter_errors(
            candidate.model_dump(by_alias=True))]

        # Add edge relationship validation
        edge_errors = self._validate_edge_relationships(candidate)
        errors.extend(edge_errors)

        return errors

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
