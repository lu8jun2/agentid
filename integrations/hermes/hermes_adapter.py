"""
Hermes Agent skill — implements agentskills.io interface.
Place this file in your Hermes skills directory and configure:

  AGENTID_API_KEY=aid_key_...
  AGENTID_OWNER_KEY_PATH=~/.agentid/owner.pem
  AGENTID_DID=did:agentid:local:...
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sdk.client import AgentIDClient

SKILL_NAME = "agentid"
REQUIRED_PERMISSIONS = ["network:outbound"]  # Hermes permission level 2


def _client() -> AgentIDClient:
    return AgentIDClient(
        agent_did=os.environ["AGENTID_DID"],
        api_key=os.environ["AGENTID_API_KEY"],
        owner_private_key_pem=open(os.path.expanduser(os.environ["AGENTID_OWNER_KEY_PATH"])).read(),
        base_url=os.getenv("AGENTID_API_URL", "https://api.agentid.dev"),
    )


def on_event(event_name: str, data: dict) -> None:
    """Hook called by Hermes runtime on lifecycle events."""
    c = _client()
    handlers = {
        "task.complete": lambda d: c.record_task_completed(
            d.get("task_id", ""), d.get("task_type", ""), d.get("duration_ms", 0), d.get("domain", "")
        ),
        "task.fail": lambda d: c.record_task_failed(d.get("task_id", ""), d.get("reason", "")),
        "token.consumed": lambda d: c.record_tokens_consumed(
            d.get("tokens", 0), d.get("model", ""), d.get("task_id", ""), d.get("domain", "")
        ),
        "project.join": lambda d: c.record_project_join(
            d.get("project_id", ""), d.get("project_name", ""), d.get("role", "participant")
        ),
        "project.leave": lambda d: c.record_project_leave(d.get("project_id", ""), d.get("outcome", "")),
        "collaboration.start": lambda d: c.record_collaboration(d.get("peer_did", ""), d.get("type", "task")),
        "peer.rate": lambda d: c.submit_peer_rating(
            d.get("target_did", ""), float(d.get("score", 5.0)), d.get("comment", ""), d.get("domain", "")
        ),
    }
    if handler := handlers.get(event_name):
        try:
            handler(data)
        except Exception as e:
            print(f"[agentid] Event recording failed: {e}", flush=True)


def get_score(did: str | None = None) -> dict:
    return _client().get_score(did)


def leaderboard(domain: str | None = None) -> list:
    return _client().leaderboard(domain)
