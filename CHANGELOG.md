## Unreleased

### Breaking Changes

- Project structure rebuilt: AP endpoints moved from `aps/` to `analytical_patterns/` module
- Removed standalone `health`, `aps`, and `tasks` routers in favour of consolidated routing

### Features

- Add `POST /analytical_patterns/compose` endpoint to combine multiple analytical patterns into one
- Add composed AP fixtures and generated output examples under `assets/composed/` and `generated/`

### Chores

- Update devcontainer to use `docker-compose.dev.yml` and revised post-create script
- Add `docker-compose.yml` for local stack bring-up
- Refresh documentation (architecture, configuration, index)
- Add unit and integration tests for composer strategies (`simple` and `agentic`)
- Update `uv.lock` dependency tree
