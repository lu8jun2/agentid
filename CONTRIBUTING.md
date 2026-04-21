# Contributing to AgentID

We welcome contributions! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/YOUR_FORK/agentid.git
cd agentid
pip install -e ".[dev]"
pytest tests/unit/ -v
docker-compose up -d
alembic upgrade head
```

## Running Tests

```bash
# Unit tests (no DB required)
pytest tests/unit/ -v

# Integration tests (requires PostgreSQL)
pytest tests/integration/ -v
```

## Project Structure

```
agentid/
├── agentid/api/routes/    # FastAPI route handlers
├── agentid/core/         # Business logic (DID, scoring, friend network)
├── agentid/models/       # SQLAlchemy ORM models
├── agentid/worker/       # Background scheduler
├── sdk/                  # Python SDK
└── tests/                # Unit + integration tests
```

## Adding New Event Types

1. Add to `VALID_EVENT_TYPES` in `agentid/api/routes/events.py`
2. Update `_recalculate_agent_score` in `agentid/worker/scheduler.py` to handle the new type
3. Add unit tests in `tests/unit/test_core.py`

## Adding New API Routes

1. Create route file in `agentid/api/routes/`
2. Register in `agentid/api/app.py`
3. Add corresponding SDK method in `sdk/client.py`
4. Add tests

## Pull Request Guidelines

- Run `pytest tests/unit/ -v` before submitting
- New features require unit tests
- Update `docs/changelog_YYYYMMDD.md` with changes
- Keep PRs focused — one feature per PR

## Open Source Philosophy

AgentID follows a **core free, services priced** model:

| Layer | License | Who pays |
|---|---|---|
| AgentID Core (this repo) | MIT | Free for everyone |
| Integration SDKs | MIT | Free |
| Agent Marketplace platforms | Commercial license | Platforms (e.g. agentworker) |
| Phase 2 on-chain services | Commercial | Enterprise integrations |

See `README.md` for the full business model explanation.
