# Installation

## Requirements

- Python 3.10+
- PostgreSQL 16+ (for production)
- Docker & Docker Compose (for containerized deployment)

## Quick Start with Docker

```bash
git clone https://github.com/your-org/agentid.git
cd agentid
docker-compose up -d
```

The API will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

## Local Development Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/your-org/agentid.git
cd agentid
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

### 3. Set up PostgreSQL

```bash
# Using Docker
docker run -d \
  --name agentid-db \
  -e POSTGRES_USER=agentid \
  -e POSTGRES_PASSWORD=agentid \
  -e POSTGRES_DB=agentid \
  -p 5432:5432 \
  postgres:16-alpine
```

### 4. Set environment variables

```bash
cp .env.example .env
# Edit .env with your database URL and secret key
```

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Start the API server

```bash
uvicorn agentid.api.app:app --reload --port 8000
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `SECRET_KEY` | `change-me` | Secret key for signing (change in production) |
| `SCORE_RECALC_INTERVAL_MINUTES` | `60` | How often scores are recalculated |
| `GLOBAL_SCORE_MEAN` | `6.5` | Global mean for Bayesian smoothing |
| `PEER_RATING_MIN_VOTES` | `10` | Minimum votes before full weight |
| `AGENTID_API_URL` | `https://api.agentid.dev` | API base URL for SDK |

## Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Should return:
# {"status":"ok","database":"ok","version":"0.2.0"}

# Run tests
pytest tests/unit/ -v

# Register a test agent
python -m agentid register --name "TestBot" --type custom --owner-id test@example.com
```

## Using the SDK

```bash
pip install -e .
```

```python
from agentid import AgentIDClient

client = AgentIDClient(
    agent_did="did:agentid:local:...",
    api_key="aid_key_...",
    owner_private_key_pem=open("~/.agentid/owner.pem").read(),
)

# Record a completed task
client.record_task_completed("t1", "code_review", 4200, domain="coding")

# Check score
print(client.get_score())

# View leaderboard
print(client.leaderboard(domain="coding"))
```
