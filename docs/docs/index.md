# Analytical Pattern Management API

[![Commit activity](https://img.shields.io/github/commit-activity/m/datagems-eosc/ap-management)](https://img.shields.io/github/commit-activity/m/datagems-eosc/ap-management)
[![License](https://img.shields.io/github/license/datagems-eosc/ap-management)](https://img.shields.io/github/license/datagems-eosc/ap-management)

This is the documentation site for the Analytical Pattern Management service. The service provides a RESTful API for **composing** Analytical Patterns.

## What are Analytical Patterns?

An **Analytical Pattern** (AP) is a graph-based representation of a sequence of data transformations. An AP is composed of **Operators**, which take one or several typed inputs to produce typed outputs.

Analytical Patterns are used to understand, document, and analyze complex data workflows and data provenance.

![ap](./images/ap-structure.png)

## Key Features

| Feature | Description |
|---------|-------------|
| AP Composition | Merge two PG-JSON APs into a single composed AP via `POST /analytical-patterns/compose` |
| Simple strategy | Exact type-matching between AP1's last operator outputs and AP2's first operator inputs |
| Agentic strategy | LLM-based semantic mapping (via LiteLLM) for cases where types or names differ |
| Validation | Composed AP is validated against the MoMa Management service before being returned |

## Quick Links

- [API](openapi.md) - OpenAPI specification
- [Configuration](configuration.md) - How to configure the service
- [Architecture](architecture.md) - Technical architecture details

## Getting Started

The best solution is to use the provided `.devcontainer` file — the MoMa Management service will already be configured.

To run it locally without the devcontainer:

```bash
# Requirements: Python >=3.12, uv, a running MoMa Management instance
uv sync --all-groups
cp .env.example .env
# Fill in the required variables in .env
uv run ap_management/main.py
```

The API will be available at `http://localhost:5000`.

### Interactive Documentation

- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc
