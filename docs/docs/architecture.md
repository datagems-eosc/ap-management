# Service Architecture

The Analytical Pattern Management service is a RESTful API service designed to manage Analytical Patterns (AP) stored in Neo4j. This document outlines the key components and their interactions.

## High-Level Architecture

The Analytical Pattern Management service follows a layered architecture:

```
┌─────────────────────────────────────────┐
│       FastAPI REST API Layer            │
│                                         │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│      Business Logic (Services) Layer    │
|                                         |
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│    Data Access / Repository Layer       │
|      (Maps business object to their     |
      physical representation on storage) |
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Neo4j Database                  │
└─────────────────────────────────────────┘
```

### Data Models

#### Analytical Pattern Structure

An Analytical Pattern is represented in [**PG-JSON**](https://pg-format.github.io/) format:

```
{
  "nodes": [
    {
      "id": "unique-id",
      "labels": ["Label1", "Label2"],
      "properties": { ... }
    },
    ...
  ],
  "edges": [
    {
      "from_": "source-id",
      "to": "target-id",
      "labels": ["RelationType"],
      "properties": { ... }
    },
    ...
  ]
}
```

**Additional Requirements for a PG-JSON graph to be an Analytical Pattern**:
- Exactly one root node with label `Analytical_Pattern`
- All nodes reachable from root


## Key Design Patterns

### Dependency Injection

The service uses a DI container (defined in `di.py`) to manage dependencies:
- Service instances are created with their repositories
- Repositories are created with database connections
- Enables easier testing and component isolation