# Service Architecture

The Analytical Pattern Management service is a RESTful API that **plans** an Analytical Pattern (AP) for a natural-language task and **composes** APs into larger ones. This document describes the key components and their interactions.

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

## Planning Pipeline

```
  HTTP client
      │  POST /api/v1/aps/plan
      │  { task, dataset_ids, allow_magic_operator }
      ▼
┌──────────────────────────────────────────────────────────┐
│  Planner  (services/planner.py)                          │
│                                                          │
│  1. Fetch each dataset from MoMa, project a              │
│     DatasetSummary (kinds, tables, access urls)          │
│  2. Matchmaker: LLM + search_aps tool → ordered steps    │
│  3. Fetch each step's AP; build magic APs for gap steps  │
│  4. Compose the chain left-to-right (Composer)           │
│  5. Reject the plan if no dataset is compatible with it  │
│  6. Suggest a value for every unwired operator input     │
└──────────────────────────────────────────────────────────┘
```

### Datasets constrain operator choice

A dataset's type determines which operators can apply to it: a SQL operator needs a
`RelationalDatabase`/`Table`/`CsvSet`, a PDF operator needs a `PdfSet`. That rule lives in
`internal/dataset_compat.py` as a small declarative table keyed by operator label
fragment; an operator matching no entry is dataset-agnostic, so a newly added operator is
never silently dropped.

Compatibility is used twice:

- **Advisorily**, in the Matchmaker: each `search_aps` result is annotated with
  `compatible_dataset_ids`, and the prompt tells the model to reject an AP whose list is
  empty. Annotating rather than filtering lets the model explain a mismatch instead of
  reasoning around an empty result set.
- **As a hard check**, at the end of planning: if datasets were supplied and the composed
  AP is compatible with none of them, the plan fails with `422` rather than returning an
  AP that cannot run.

The datasets themselves never enter the AP graph — the planned AP holds no dataset nodes,
it is only guaranteed to be compatible with them.

### The magic operator

When `allow_magic_operator` is set, the Matchmaker may return the sentinel id `magic` for
a step no catalogued AP covers, and the planner builds a single-operator AP around the
generic LLM-backed [magic operator](https://github.com/SoTrx/ap-executor/tree/master/magic_operator).
The same builder answers the whole task when the catalogue matches nothing at all.

The magic operator's `instruction` is generated at plan time but delivered at *run* time
as an input value, because the AP Executor forwards only an operator's declared inputs and
never its node properties. It is marked `"wiring": "parameter"` on the node so the Composer
knows not to satisfy it from an upstream operator's outputs — the payload input beside it
is ordinary dataflow and gets wired normally.

The sentinel is only described to the model when the caller allows it, so a default request
gets byte-identical instructions, and an uncovered task still returns `404`.

### Instantiation parameters

The planner returns one `SuggestedParameter` per operator input that is *not* already
satisfied by an incoming `input` edge, tagged with its `operator_id`. This mirrors the AP
Executor's `ApInstance.state` (`{operator_id: {name: value}}`), so a plan can be handed
straight to `POST /api/v1/aps/execute`. A suggestion failure never fails the plan: the
`ValueSuggester` falls back to each parameter's declared default.

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

Applies when the number of outputs of AP1's last operator equals the number of *dataflow* inputs of AP2's first operator, and every pair has the same scalar type. No external dependencies.

Inputs marked `"wiring": "parameter"` are supplied at instantiation time rather than wired from upstream, so they are excluded from the match. Every catalogued operator declares dataflow inputs only, making this a no-op for them.

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
- `get_catalog()` / `get_dataset_catalog()` — MoMa-backed AP and dataset catalogs.
- `get_magic_operator_builder()` — a `MagicOperatorBuilder` configured from `MAGIC_OPERATOR_*`.
- `get_planner()` — assembles the `Planner` from the matchmaker, composer, both catalogs, the value suggester and the magic operator builder.
