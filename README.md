# AP Management

[![Commit activity](https://img.shields.io/github/commit-activity/m/datagems-eosc/ap-management)](https://img.shields.io/github/commit-activity/m/datagems-eosc/ap-management)
[![License](https://img.shields.io/github/license/datagems-eosc/ap-management)](https://img.shields.io/github/license/datagems-eosc/ap-management)

## Overview

An **Analytical Pattern** (AP) is a graph-based representation of a sequence of data transformations, composed of **Operators** that take one or several typed inputs to produce typed outputs.

This service provides a single REST endpoint to **compose** two APs into one: it finds a mapping between the outputs of the first AP and the inputs of the second, then stitches the two graphs together.

## Features

- **AP Composition** – `POST /analytical-patterns/compose` merges two PG-JSON APs into a composed AP.
- **Simple strategy** – exact type-matching between AP1's last operator outputs and AP2's first operator inputs (no LLM required).
- **Agentic strategy** – an LLM (via [LiteLLM](https://docs.litellm.ai/)) finds semantic mappings when types or names differ (e.g. `query` → `sql`).
- **Validation** – the composed AP is validated via the [MoMa Management](https://github.com/datagems-eosc/moma-management) service.

## Quick Start

```bash
# You can remove '--all-groups' for production
uv sync --all-groups
cp .env.example .env
# Fill in the required variables in .env (see Configuration below)
uv run ap_management/main.py
```

The API will be available at `http://localhost:5000`.  
Interactive docs: `http://localhost:5000/docs`

## Configuration

Configuration is managed through environment variables (see `.env.example`):

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MOMA_MANAGEMENT_BASE_URL` | Base URL of the MoMa Management service | `http://moma-management:5000` | No |
| `LLM_API_BASE` | Base URL of the LLM API (OpenAI-compatible) | – | Yes (agentic strategy) |
| `LLM_API_MODEL` | Model identifier passed to LiteLLM | – | Yes (agentic strategy) |
| `LLM_API_KEY` | API key for the LLM provider | – | No |
| `LLM_SSL_VERIFY` | Verify TLS certificates when calling the LLM | `true` | No |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | – | No |
| `ROOT_PATH` | API root path for reverse-proxy deployments | – | No |
| `MOMA_VERSION` | MoMa Management image version (used in docker-compose) | – | No |

## Testing

Tests spin up a containerised MoMa Management instance via [testcontainers](https://testcontainers.com/). No manual configuration needed beyond setting `MOMA_VERSION` in `.env`:

```bash
pytest tests/
```

## Documentation

Full documentation is available at: https://datagems-eosc.github.io/ap-management/
