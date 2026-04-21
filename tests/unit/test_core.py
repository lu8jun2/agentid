"""Unit tests for core modules."""
import pytest
from datetime import datetime
from agentid.core.did import generate_did, generate_keypair, did_to_uuid
from agentid.core.signing import sign, verify, hash_str
from agentid.core.anti_tamper import compute_event_hash, verify_chain
from agentid.core.scoring import ScoreInput, compute_score


def test_did_generation():
    did = generate_did()
    assert did.startswith("did:agentid:local:")
    uid = did_to_uuid(did)
    assert len(uid) == 36


def test_keypair_and_signing():
    priv, pub = generate_keypair()
    assert "PRIVATE KEY" in priv
    assert "PUBLIC KEY" in pub
    data = b"hello agentid"
    sig = sign(priv, data)
    assert verify(pub, data, sig)
    assert not verify(pub, b"tampered", sig)


def test_event_hash_deterministic():
    ts = datetime(2026, 4, 19, 12, 0, 0)
    h1 = compute_event_hash("id1", "agent1", "TASK_COMPLETED", {"task_id": "t1"}, ts, None)
    h2 = compute_event_hash("id1", "agent1", "TASK_COMPLETED", {"task_id": "t1"}, ts, None)
    assert h1 == h2
    h3 = compute_event_hash("id1", "agent1", "TASK_COMPLETED", {"task_id": "t1"}, ts, "prevhash")
    assert h1 != h3


def test_chain_verification():
    class FakeEvent:
        def __init__(self, id, agent_id, event_type, payload, timestamp, prev_hash, event_hash):
            self.id = id
            self.agent_id = agent_id
            self.event_type = event_type
            self.payload = payload
            self.timestamp = timestamp
            self.prev_hash = prev_hash
            self.event_hash = event_hash

    ts1 = datetime(2026, 4, 19, 10, 0, 0)
    ts2 = datetime(2026, 4, 19, 11, 0, 0)
    h1 = compute_event_hash("e1", "a1", "TASK_COMPLETED", {}, ts1, None)
    h2 = compute_event_hash("e2", "a1", "TOKEN_CONSUMED", {"tokens": 100}, ts2, h1)

    e1 = FakeEvent("e1", "a1", "TASK_COMPLETED", {}, ts1, None, h1)
    e2 = FakeEvent("e2", "a1", "TOKEN_CONSUMED", {"tokens": 100}, ts2, h1, h2)

    valid, broken = verify_chain([e1, e2])
    assert valid
    assert broken is None

    # Tamper e2
    e2.event_hash = "tampered"
    valid, broken = verify_chain([e1, e2])
    assert not valid
    assert broken == "e2"


def test_scoring_new_agent():
    inp = ScoreInput()
    result = compute_score(inp)
    assert 0.0 <= result["score"] <= 10.0
    assert "components" in result
    assert "domain_scores" in result


def test_scoring_with_data():
    inp = ScoreInput(
        project_count=5,
        active_projects=3,
        total_tokens=50000,
        tasks_completed=20,
        collaboration_count=8,
        account_age_days=180,
        peer_ratings=[8.0, 7.5, 9.0, 8.5, 8.0, 7.5, 9.0, 8.5, 8.0, 7.5, 9.0, 8.5],
        domain_events={"coding": {"tasks": 15, "tokens": 30000, "peer_ratings": [8.0, 9.0]}},
    )
    result = compute_score(inp)
    assert result["score"] > 5.0
    assert "coding" in result["domain_scores"]


def test_peer_rating_bayesian_smoothing():
    # New agent with 1 rating should be pulled toward global mean
    inp_few = ScoreInput(peer_ratings=[10.0])
    inp_many = ScoreInput(peer_ratings=[10.0] * 50)
    r_few = compute_score(inp_few)
    r_many = compute_score(inp_many)
    # More ratings = higher score when ratings are above mean
    assert r_many["components"]["peer_rating_score"] > r_few["components"]["peer_rating_score"]
