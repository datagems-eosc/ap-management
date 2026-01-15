# AP Management

[![Commit activity](https://img.shields.io/github/commit-activity/m/datagems-eosc/provenance-demo)](https://img.shields.io/github/commit-activity/m/datagems-eosc/provenance-demo)
[![License](https://img.shields.io/github/license/datagems-eosc/provenance-demo)](https://img.shields.io/github/license/datagems-eosc/provenance-demo)

## Overview

An **Analytical Pattern** (AP) is a graph-based representation of a sequence of data transformations. An AP is composed of **Operators**, which can take one or several inputs to produce an output.

Analytical Patterns are used to understand, document, and analyze complex data workflows and data provenance.

## Quick Start

```bash
# You can remove '--all-groups' for production
uv sync --all-groups
cp .env.example .env
# (Fill all the required variable in .env)
uv run ap_management/main.py
```

## Configuration

Configuration is managed through environment variables (see `.env` file):

- `NEO4J_URI`: Neo4j connection URI
- `NEO4J_USERNAME`: Neo4j username
- `NEO4J_PASSWORD`: Neo4j password

## Testing

Run tests with pytest:

```bash
pytest tests/
```

Tests use testcontainers to run a Neo4j instance automatically.

## Documentation

Full API documentation is available in the [docs](docs/) directory, including:

- [API Overview](docs/docs/api-overview.md)
- [Architecture](docs/docs/architecture.md)
- [Configuration](docs/docs/configuration.md)
- [Deployment](docs/docs/deployment.md)
