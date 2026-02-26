# AP Management

[![Commit activity](https://img.shields.io/github/commit-activity/m/datagems-eosc/provenance-demo)](https://img.shields.io/github/commit-activity/m/datagems-eosc/provenance-demo)
[![License](https://img.shields.io/github/license/datagems-eosc/provenance-demo)](https://img.shields.io/github/license/datagems-eosc/provenance-demo)

## Overview

An **Analytical Pattern** (AP) is a graph-based representation of a sequence of data transformations. An AP is composed of **Operators**, which can take one or several inputs to produce an output.

Analytical Patterns are used to understand, document, and analyze complex data workflows and data provenance.

## Features

- **CRUD** – Create, retrieve, and list Analytical Patterns stored in Neo4j.
- **Semantic search** – Search APs by natural language query. Descriptions are embedded at creation time using a local [`sentence-transformers`](https://www.sbert.net/) model (`all-MiniLM-L6-v2`) and stored as Neo4j vector properties. At query time the same model embeds the query and Neo4j performs an approximate nearest-neighbour search, returning each match with a cosine-similarity score.
  > **Neo4j requirement**: vector indexes require **Neo4j 5.11+** (Community or Enterprise).

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

> **Note**: Semantic search requires Neo4j 5.11+. The embedding model (`all-MiniLM-L6-v2`) is downloaded automatically on first startup from Hugging Face and cached locally.

## Testing

Run tests with pytest:

```bash
pytest tests/
```

Tests use testcontainers to run a Neo4j instance automatically.

## Documentation

Full documentation is available at: https://datagems-eosc.github.io/ap-management/
