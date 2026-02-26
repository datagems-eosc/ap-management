# Configuration

This document describes how to configure the Analytical Pattern Management service for different environments.

## Environment Variables

The Analytical Pattern Management service uses environment variables for configuration. A `.env` file can be used to define these variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `NEO4J_URI` | Neo4j database connection URI | `neo4j://localhost:7687` | Yes |
| `NEO4J_USERNAME` | Neo4j database username | `neo4j` | Yes |
| `NEO4J_PASSWORD` | Neo4j database password | - | Yes |
| `SCHEMA_REGISTRY_BASE_URL` | Base URL for remote schema validation service | `http://172.17.0.1:8085` | No |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | - | No |
| `ROOT_PATH` | API root path for reverse proxy deployments | - | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` | No |
| `APP_ENV` | Application environment (dev, prod) | `dev` | No |

## Semantic Search

The service embeds AP descriptions with a local [`sentence-transformers`](https://www.sbert.net/) model (`all-MiniLM-L6-v2`) and stores them as vector properties in Neo4j.

**Requirements**:

- **Neo4j 5.11+** – vector index support (`CREATE VECTOR INDEX`) is only available from this version onward.
- The model is downloaded from Hugging Face on **first startup** and cached in the default `sentence-transformers` cache directory (`~/.cache/torch/sentence_transformers`). Subsequent restarts load the model from disk and incur no network traffic.

> If the Neo4j instance is older than 5.11, the application will log an error during startup and the `/api/v1/aps/?q=...` search endpoint will return `500`.

### Example `.env` File

```bash
# Neo4j Configuration
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password

# Schema Validation
SCHEMA_REGISTRY_BASE_URL=http://schema-service:8085

# CORS (optional - comma-separated origins)
CORS_ORIGINS=http://localhost:5173,https://your-frontend.com

# Logging
LOG_LEVEL=INFO

# Application Environment
APP_ENV=dev
```

## API Documentation

Once configured and running, access the interactive API documentation:

- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc
- **OpenAPI JSON**: http://localhost:5000/openapi.json

## Testing Configuration

Tests automatically use testcontainers to spin up a Neo4j instance. No manual configuration needed for running tests:

```bash
pytest tests/
```

The test configuration is defined in `tests/conftest.py`.
