# AP Management

[![Commit activity](https://img.shields.io/github/commit-activity/m/datagems-eosc/ap-management)](https://img.shields.io/github/commit-activity/m/datagems-eosc/ap-management)
[![License](https://img.shields.io/github/license/datagems-eosc/ap-management)](https://img.shields.io/github/license/datagems-eosc/ap-management)

## Overview

An **Analytical Pattern** (AP) is a graph-based representation of a sequence of data transformations, composed of **Operators** that take one or several typed inputs to produce typed outputs.

This service **plans** an AP for a natural-language task and **composes** existing APs into larger ones.

Planning is the entry point used by MoMa: a natural-language request first goes to [cross-dataset-discovery](https://github.com/datagems-eosc/cross-dataset-discovery), which returns the ids of the relevant datasets; those ids are then passed to `POST /api/v1/aps/plan` along with the task. The planner picks the APs that answer the task *and* can actually run on that data, composes them, and returns the AP together with the parameters needed to instantiate it.

## Features

- **AP Planning** – `POST /api/v1/aps/plan` turns a natural-language task into a runnable AP.
- **Dataset-aware** – dataset ids constrain which operators can apply (a SQL operator needs a relational or tabular dataset, not a PDF corpus) and ground the suggested parameter values. The planned AP contains no dataset nodes; it is only guaranteed to be *compatible* with them.
- **Magic operator** – opt-in per request, fills a step no catalogued AP covers with a generic LLM-backed operator.
- **AP Composition** – `POST /analytical-patterns/compose` merges two PG-JSON APs into a composed AP.
- **Simple strategy** – exact type-matching between AP1's last operator outputs and AP2's first operator inputs (no LLM required).
- **Agentic strategy** – an LLM (via [LiteLLM](https://docs.litellm.ai/)) finds semantic mappings when types or names differ (e.g. `query` → `sql`).
- **Validation** – the composed AP is validated via the [MoMa Management](https://github.com/datagems-eosc/moma-management) service.

## Planning an AP

```bash
curl -X POST http://localhost:5000/api/v1/aps/plan \
  -H 'Content-Type: application/json' \
  -d '{
        "task": "List all students older than 30",
        "dataset_ids": ["d1000000-0000-4000-8000-000000000001"],
        "allow_magic_operator": false
      }'
```

| Field | Default | Meaning |
|---|---|---|
| `task` | – | The natural-language task to plan for. |
| `dataset_ids` | `[]` | Datasets the plan must run against, as returned by cross-dataset-discovery. |
| `allow_magic_operator` | `false` | Allow uncovered steps to be filled by a generic LLM operator instead of failing with `404`. |

The response carries the AP, the datasets it was planned against, and
`instantiation_parameters`: one entry per operator input that is not already wired from
an upstream operator, each tagged with the `operator_id` it belongs to. That keying
matches the AP Executor's `ApInstance.state` (`{operator_id: {name: value}}`), so a
caller can hand the plan straight to `POST /api/v1/aps/execute`.

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
| `MAGIC_OPERATOR_NAME` | Operator node name the planner emits for a magic step; slugified into its Consul service name | `Magic Operator` | No |
| `MAGIC_OPERATOR_VERSION` | Pins the magic operator's Consul lookup to a `Service.Meta.version` | – | No |

> Using the magic operator requires a deployed [magic operator](https://github.com/SoTrx/ap-executor/tree/master/magic_operator) registered in Consul under the slugified `MAGIC_OPERATOR_NAME`, whose own config declares an `instruction` input and a payload input. See [Configuration](docs/docs/configuration.md) for the exact contract.

## Testing

Tests spin up a containerised MoMa Management instance via [testcontainers](https://testcontainers.com/). No manual configuration needed beyond setting `MOMA_VERSION` in `.env`:

```bash
pytest tests/
```

## Documentation

Full documentation is available at: https://datagems-eosc.github.io/ap-management/
