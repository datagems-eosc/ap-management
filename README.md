# AP Management

[![Commit activity](https://img.shields.io/github/commit-activity/m/datagems-eosc/provenance-demo)](https://img.shields.io/github/commit-activity/m/datagems-eosc/provenance-demo)
[![License](https://img.shields.io/github/license/datagems-eosc/provenance-demo)](https://img.shields.io/github/license/datagems-eosc/provenance-demo)

## Overview

AP Management (Analytical Pattern Management) is a RESTful API service for managing Analytical Patterns in a Neo4j graph database. An Analytical Pattern is a graph-based representation of data lineage, transformations, and dependencies using nodes and edges.

## Features

- **Create Analytical Patterns**: Register new Analytical Patterns in PG-JSON format
- **Retrieve Analytical Patterns**: Fetch complete AP graphs by UUID
- **Validate Analytical Patterns**: Ensure APs conform to required structure and constraints
- **Visualize Analytical Patterns**: Generate SVG diagrams of AP graph structures
- **Manage Tasks**: Create tasks and associate them with multiple Analytical Patterns
- **Health Checks**: Monitor service availability

## Technology Stack

- **Framework**: FastAPI (Python 3.12+)
- **Database**: Neo4j 6.0+
- **Graph Visualization**: Graphviz
- **Data Validation**: Pydantic v2
- **Testing**: pytest with testcontainers

## Quick Start

### Prerequisites

- Python 3.12+
- Neo4j 6.0+
- Docker (for running tests with testcontainers)

### Installation

```bash
pip install -e .
```

### Running the API

```bash
python -m ap_management.main
```

The API will be available at `http://localhost:5000/api/v1`

### Documentation

View the API documentation at `http://localhost:5000/docs` (Swagger UI)

## Project Structure

```
ap_management/
├── api/               # REST API endpoints and handlers
│   └── v1/
│       ├── aps/      # Analytical Pattern endpoints
│       ├── tasks/    # Task management endpoints
│       └── health.py # Health check endpoint
├── domain/           # Domain models and business logic
├── services/         # Business logic services
├── repository/       # Data access layer (Neo4j)
└── di.py            # Dependency injection setup
```

## API Endpoints

### Analytical Patterns

- `POST /api/v1/aps` - Create a new Analytical Pattern
- `GET /api/v1/aps/{id}` - Retrieve an Analytical Pattern
- `POST /api/v1/aps/validate` - Validate an Analytical Pattern
- `POST /api/v1/aps/display` - Generate SVG visualization

### Tasks

- `POST /api/v1/tasks` - Create a new Task
- `GET /api/v1/tasks/{id}/aps` - Get APs associated with a Task

### Health

- `GET /api/v1/health` - Check service health

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

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Build Documentation

```bash
mkdocs serve
```

Documentation will be available at `http://localhost:8000`

## License

See the [LICENSE](LICENSE) file for details.

## Author

Lucas Peirone - lucas.peirone@univ-grenoble-alpes.fr
