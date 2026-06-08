# Service Architecture

The Analytical Pattern Management service is a RESTful API that **composes** two Analytical Patterns (APs) into a single AP. This document describes the key components and their interactions.

## High-Level Architecture

```
  HTTP client
      │
      │  POST /analytical-patterns/compose
      │  { ap1: {...}, ap2: {...} }
      ▼
┌─────────────────────────────────────────┐
│       FastAPI REST API Layer            │
│  ap_management/api/v1/                  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│        Composer Service                 │
│  ap_management/services/composer/       │
│                                         │
│  1. Select a composition strategy       │
│  2. Generate output→input mapping       │
│  3. Stitch the two graphs together      │
│  4. Validate via MoMa Management        │
└──────┬──────────────────────┬───────────┘
       │                      │
┌──────▼──────┐    ┌──────────▼──────────┐
│   Simple    │    │  Agentic            │
│  Strategy   │    │  Strategy           │
│             │    │  (LiteLLM → LLM)    │
└─────────────┘    └─────────────────────┘
                              │
              ┌───────────────▼──────────────┐
              │     MoMa Management API      │
              │  (AP storage & validation)   │
              └──────────────────────────────┘
```

## Data Models

### Analytical Pattern Structure

An Analytical Pattern is represented in [**PG-JSON**](https://pg-format.github.io/) format:

```json
{
  "nodes": [
    {
      "id": "unique-id",
      "labels": ["Label1", "Label2"],
      "properties": { "inputs": [...], "outputs": [...] }
    }
  ],
  "edges": [
    {
      "from": "source-id",
      "to": "target-id",
      "labels": ["RelationType"],
      "properties": {}
    }
  ]
}
```

**Requirements for a valid AP:**
- Exactly one root node with label `Analytical_Pattern`
- All nodes reachable from root
- Each `Operator` node has `inputs` and `outputs` properties (arrays of `{ name, type }` objects)

## Composition Pipeline

### Step 1 — Strategy Selection

The `Composer` iterates over registered strategies in order and selects the first one whose `is_possible()` check passes:

| Strategy | Condition |
|----------|-----------|
| `SimpleComposition` | AP1's last operator outputs and AP2's first operator inputs have the same length **and** matching types in order |
| `AgenticComposition` | Always attempted as a fallback; uses an LLM to decide compatibility |

### Step 2 — Mapping Generation

A **Mapping** pairs an output parameter of AP1's last operator with an input parameter of AP2's first operator:

```
Mapping {
  source:      { node_id, name, path, type }   ← AP1 last operator output
  destination: { node_id, name, path, type }   ← AP2 first operator input
  confidence:  float (0–1)
  reason:      str
}
```

- `SimpleComposition` generates mappings by zipping outputs and inputs in order (confidence = 1.0).
- `AgenticComposition` sends the operator schemas to the LLM and parses a structured `ComposeReport` response.

### Step 3 — Stitching

For each mapping the `Composer._stitch()` method:

1. Creates a `ResultType` node bridging the AP1 output to the AP2 input, with `output` and `input` edges carrying `mapping` properties that describe the data transformation path.
2. Copies all non-`Analytical_Pattern` nodes and edges from AP2 into AP1.
3. Re-assigns all `consist_of` edges to point to AP1's (new) root `Analytical_Pattern` node.
4. Adds a `follows` edge from AP2's first operator to AP1's last operator.

### Step 4 — Validation

The composed AP is sent to the **MoMa Management** service (`/api/v1/aps/validate`) for schema validation. A failed validation raises a `CompositionInternalError` (HTTP 500).

## Composition Strategies

### SimpleComposition

Applies when the number of outputs of AP1's last operator equals the number of inputs of AP2's first operator, and every pair has the same scalar type. No external dependencies.

### AgenticComposition

Always applicable as a fallback. Sends the operator schemas to an LLM via [LiteLLM](https://docs.litellm.ai/) and expects a structured JSON response:

- Compatible: returns a list of `Mapping` objects with source/destination paths.
- Incompatible: returns `{ compatible: false, reason: "..." }`, which causes a `CompositionInputError` (HTTP 422).

The LLM endpoint is configured via `LLM_API_BASE` / `LLM_API_MODEL` environment variables (any OpenAI-compatible API is supported).

## Dependency Injection

Dependencies are wired in `ap_management/di.py` using FastAPI's `Depends` mechanism:

- `get_llm()` — builds an `LLM` instance from `LLM_API_*` env vars.
- `get_moma_svc()` — builds a Kiota-generated `MomaManagementClient` pointed at `MOMA_MANAGEMENT_BASE_URL`.
- `get_composer()` — assembles a `Composer` with both strategies and the MoMa client.
