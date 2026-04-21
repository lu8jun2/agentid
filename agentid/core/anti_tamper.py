"""Tamper-evident event chain: hash chaining + verification."""
import json
import hashlib
from datetime import datetime


def compute_event_hash(
    event_id: str,
    agent_id: str,
    event_type: str,
    payload: dict,
    timestamp: datetime,
    prev_hash: str | None,
) -> str:
    canonical = json.dumps({
        "id": event_id,
        "agent_id": agent_id,
        "event_type": event_type,
        "payload": payload,
        "timestamp": timestamp.isoformat(),
        "prev_hash": prev_hash or "",
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_chain(events: list) -> tuple[bool, str | None]:
    """
    Walk the event chain for one agent in chronological order.
    Returns (is_valid, first_broken_event_id or None).
    """
    prev_hash = None
    for event in sorted(events, key=lambda e: e.timestamp):
        expected = compute_event_hash(
            event.id, event.agent_id, event.event_type,
            event.payload, event.timestamp, prev_hash,
        )
        if event.event_hash != expected:
            return False, event.id
        prev_hash = event.event_hash
    return True, None
