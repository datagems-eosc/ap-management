# Configuration

This document describes how to configure the Analytical Pattern Management service.

## Environment Variables

The service is configured via environment variables. A `.env` file can be used to define them (see `.env.example`):

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MOMA_MANAGEMENT_BASE_URL` | Base URL of the MoMa Management service used for AP validation | `http://moma-management:5000` | No |
| `LLM_API_BASE` | Base URL of an OpenAI-compatible LLM API | – | Yes (agentic strategy) |
| `LLM_API_MODEL` | Model identifier passed to LiteLLM (e.g. `openai/gpt-4o`) | – | Yes (agentic strategy) |
| `LLM_API_KEY` | API key for the LLM provider | – | No |
| `LLM_SSL_VERIFY` | Verify TLS certificates when calling the LLM (`true`/`false`) | `true` | No |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | – | No |
| `ROOT_PATH` | API root path for reverse-proxy deployments | – | No |
| `MOMA_VERSION` | MoMa Management Docker image version (used by docker-compose and tests) | – | No |

> The `LLM_*` variables are only required when the **agentic composition strategy** is needed (i.e. when AP outputs and inputs don't match by type). The `SimpleComposition` strategy works without any LLM.

## Composition Strategies

### SimpleComposition (no LLM)

Requires no additional configuration. Activates automatically when AP1's last operator outputs and AP2's first operator inputs have the same number of parameters and matching scalar types.

### AgenticComposition (LLM required)

Used as a fallback when `SimpleComposition` is not applicable. Requires an OpenAI-compatible LLM endpoint:

```bash
LLM_API_BASE=https://api.openai.com/v1
LLM_API_MODEL=openai/gpt-4o-mini
LLM_API_KEY=sk-...
```

Any LiteLLM-supported provider works. For a local model (e.g. Ollama):

```bash
LLM_API_BASE=http://localhost:11434
LLM_API_MODEL=ollama/llama3
LLM_SSL_VERIFY=false
```

## Example `.env` File

```bash
# MoMa Management service
MOMA_MANAGEMENT_BASE_URL=http://moma-management:5000
MOMA_VERSION=v2.6.0

# LLM (required for agentic composition)
LLM_API_BASE=https://api.openai.com/v1
LLM_API_MODEL=openai/gpt-4o-mini
LLM_API_KEY=sk-...

# CORS (optional — comma-separated origins)
CORS_ORIGINS=http://localhost:5173,https://your-frontend.com
```

## Docker Compose

The `docker-compose.yml` file starts the full stack (ap-management + moma-management + neo4j):

```bash
cp .env.example .env
# Set MOMA_VERSION and any LLM variables in .env
docker compose up
```

The `ap-management` service is exposed on port `5000` by default.

## API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc
- **OpenAPI JSON**: http://localhost:5000/openapi.json

## Testing

Tests spin up a containerised MoMa Management instance automatically via [testcontainers](https://testcontainers.com/). `MOMA_VERSION` must be set in `.env`:

```bash
uv sync --all-groups
pytest tests/
```
