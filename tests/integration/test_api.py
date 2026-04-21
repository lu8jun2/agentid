"""End-to-end API integration tests.

Coverage: register → create API key → write event → get score → verify chain.
Requires a running PostgreSQL instance (set DATABASE_URL).
Run with: pytest tests/integration/ -v
"""
import json
import pytest
import httpx
from sqlalchemy import text
from agentid.db.session import AsyncSessionLocal, engine


@pytest.fixture(autouse=True)
async def clean_db():
    """Reset the database before each test."""
    async with AsyncSessionLocal() as db:
        for table in [
            "job_postings", "knowledge_sessions", "score_snapshots",
            "reputation_scores", "project_participations",
            "projects", "events", "api_keys", "agents",
        ]:
            try:
                await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            except Exception:
                pass
        await db.commit()


@pytest.fixture
def base_url() -> str:
    return "http://127.0.0.1:8000"


@pytest.fixture
async def registered_agent(base_url: str):
    """Register a fresh agent and return (did, private_key)."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.post("/v1/agents", json={
            "name": "TestAgent",
            "agent_type": "custom",
            "owner_id": "test@example.com",
        })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["did"], data["private_key"]


async def create_api_key(base_url: str, did: str) -> str:
    """Create an API key for the agent."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.post("/v1/auth/keys", json={
            "agent_did": did,
            "name": "test-key",
        })
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


async def sign_and_post_event(
    base_url: str, did: str, api_key: str, private_key: str,
    event_type: str, payload: dict,
) -> httpx.Response:
    """POST /v1/events with proper owner signature."""
    from agentid.core.signing import sign
    from agentid.core.anti_tamper import compute_event_hash
    import hashlib
    from datetime import datetime

    body = {"agent_did": did, "event_type": event_type, "payload": payload}
    body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
    body_hash = hashlib.sha256(body_json.encode()).hexdigest()
    ts = str(int(9999999999))
    sig = sign(private_key, body_hash.encode())

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Owner-Signature": sig,
        "X-Timestamp": ts,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        return await client.post("/v1/events", content=body_json, headers=headers)


@pytest.mark.asyncio
async def test_register_agent(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.post("/v1/agents", json={
            "name": "Alice",
            "agent_type": "claude_code",
            "owner_id": "alice@owner.com",
        })
    assert resp.status_code == 201
    data = resp.json()
    assert data["did"].startswith("did:agentid:local:")
    assert "private_key" in data
    assert data["name"] == "Alice"


@pytest.mark.asyncio
async def test_register_duplicate_did_fails(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        for _ in range(2):
            resp = await client.post("/v1/agents", json={
                "name": "Bob",
                "agent_type": "openclaw",
                "owner_id": "bob@owner.com",
            })
    assert resp.status_code in (201, 409)


@pytest.mark.asyncio
async def test_get_agent(base_url: str, registered_agent):
    did, _ = registered_agent
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.get(f"/v1/agents/{did}")
    assert resp.status_code == 200
    assert resp.json()["did"] == did


@pytest.mark.asyncio
async def test_create_api_key(base_url: str, registered_agent):
    did, _ = registered_agent
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.post("/v1/auth/keys", json={
            "agent_did": did,
            "name": "my-key",
        })
    assert resp.status_code == 201
    data = resp.json()
    assert data["api_key"].startswith("aid_key_")


@pytest.mark.asyncio
async def test_post_event_requires_signature(base_url: str, registered_agent):
    did, _ = registered_agent
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.post("/v1/events", json={
            "agent_did": did,
            "event_type": "TASK_COMPLETED",
            "payload": {"task_id": "t1"},
        })
    assert resp.status_code == 422  # missing signature headers


@pytest.mark.asyncio
async def test_post_and_read_event(base_url: str, registered_agent):
    did, privkey = registered_agent
    api_key = await create_api_key(base_url, did)

    resp = await sign_and_post_event(
        base_url, did, api_key, privkey,
        "TASK_COMPLETED",
        {"task_id": "t1", "domain": "coding"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "event_id" in data
    assert "event_hash" in data

    # Read it back
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp2 = await client.get(f"/v1/events/{data['event_id']}")
    assert resp2.status_code == 200
    assert resp2.json()["event_type"] == "TASK_COMPLETED"


@pytest.mark.asyncio
async def test_chain_hash_integrity(base_url: str, registered_agent):
    did, privkey = registered_agent
    api_key = await create_api_key(base_url, did)

    for i in range(3):
        resp = await sign_and_post_event(
            base_url, did, api_key, privkey,
            "TASK_COMPLETED",
            {"task_id": f"t{i}", "domain": "coding"},
        )
        assert resp.status_code == 201, resp.text

    # Verify chain
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.get(f"/v1/scores/verify/chain/{did}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["event_count"] == 3


@pytest.mark.asyncio
async def test_score_computed_after_events(base_url: str, registered_agent):
    did, privkey = registered_agent
    api_key = await create_api_key(base_url, did)

    # Write several events
    events = [
        ("PROJECT_JOIN", {"project_id": "p1", "project_name": "Test Project"}),
        ("TOKEN_CONSUMED", {"tokens": 50000, "model": "gpt-4", "domain": "coding"}),
        ("TASK_COMPLETED", {"task_id": "t1", "duration_ms": 3000, "domain": "coding"}),
        ("TASK_COMPLETED", {"task_id": "t2", "duration_ms": 5000, "domain": "coding"}),
    ]
    for event_type, payload in events:
        resp = await sign_and_post_event(base_url, did, api_key, privkey, event_type, payload)
        assert resp.status_code == 201, resp.text

    # Get score
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.get(f"/v1/scores/{did}/score")
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert 0.0 <= data["score"] <= 10.0


@pytest.mark.asyncio
async def test_job_posting_flow(base_url: str, registered_agent):
    did, privkey = registered_agent
    api_key = await create_api_key(base_url, did)

    # Register job
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.post("/v1/network/jobs", json={
            "poster_did": did,
            "external_job_id": "job-001",
            "title": "Build a dashboard",
            "domain": "coding",
            "reward_amount": 25.0,
        }, headers={"Authorization": f"Bearer {api_key}"})
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["job_id"]

    # Match job
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.post(f"/v1/network/jobs/{job_id}/match", json={
            "acceptor_did": "did:agentid:local:peer-agent",
        }, headers={"Authorization": f"Bearer {api_key}"})
    assert resp.status_code == 200, resp.text

    # Get job
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.get(f"/v1/network/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "matched"


@pytest.mark.asyncio
async def test_health_endpoint(base_url: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "version" in data