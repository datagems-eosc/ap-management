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

## Semantic Search

The service supports natural language search over Analytical Patterns using vector similarity.

### How it works

```
  AP creation                         Search query
       │                                   │
       ▼                                   ▼
 LocalEmbedder                       LocalEmbedder
 (all-MiniLM-L6-v2)                 (all-MiniLM-L6-v2)
       │                                   │
       │  description vector               │  query vector
       ▼                                   ▼
  Neo4j node property          db.index.vector.queryNodes
  description_embedding        (ANN search, cosine similarity)
       │                                   │
       └──────── vector index ─────────────┘
                     │
                     ▼
          List[{ ap, score }]
```

1. **At creation time** – the `description` property of the root `Analytical_Pattern` node is embedded using `SentenceTransformer("all-MiniLM-L6-v2")` and stored on the node as `description_embedding`.
2. **At search time** – the query string is embedded with the same model and passed to `db.index.vector.queryNodes`, which performs an approximate nearest-neighbour search using the `ap_description_embedding` vector index.
3. **Response** – each result contains the full AP object and a `score` (cosine similarity, 0–1).

> The `description_embedding` property is intentionally excluded from all API responses; only the `score` is surfaced.


## Key Design Patterns

### Dependency Injection

The service uses a DI container (defined in `di.py`) to manage dependencies:
- Service instances are created with their repositories
- Repositories are created with database connections
- Enables easier testing and component isolation