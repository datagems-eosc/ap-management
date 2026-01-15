# Configuration

This document describes how to configure the Analytical Pattern Management service for different environments.

## Environment Variables

The Analytical Pattern Management service uses environment variables for configuration. A `.env` file can be used to define these variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `NEO4J_URI` | Neo4j database connection URI | `neo4j://localhost:7687` | Yes |
| `NEO4J_USERNAME` | Neo4j database username | `neo4j` | Yes |
| `NEO4J_PASSWORD` | Neo4j database password | - | Yes |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` | No |
| `APP_ENV` | Application environment (dev, prod) | `dev` | No |

### Example `.env` File

```bash
# Neo4j Configuration
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password

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
