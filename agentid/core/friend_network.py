"""Friend relationship network: friend list management + broadcast logic."""
import random
from datetime import datetime
from dataclasses import dataclass

MAX_FRIENDS = 200
INITIAL_BATCH = 6   # initial friends when first registered
BATCH_SIZE = 6      # batch added when friend count reaches next 6

# Broadcast fan-out: when friend count >= 20, use 3 instead of 6
BROADCAST_FANOUT_FULL = 6
BROADCAST_FANOUT_REDUCED = 3
FRIEND_COUNT_THRESHOLD = 20


@dataclass
class FriendInfo:
    did: str
    score: float
    domain: str | None
    friend_since: datetime


def select_friends_for_broadcast(friend_dids: list[str], friend_scores: dict[str, float] | None = None) -> list[str]:
    """Select friends to broadcast to.

    Rules:
    - Friend count < 6: not yet established, skip
    - Friend count 6-19: broadcast to 6 random friends
    - Friend count 20-200: broadcast to 3 random friends (security threshold)
    """
    count = len(friend_dids)
    if count < INITIAL_BATCH:
        return []
    fanout = BROADCAST_FANOUT_REDUCED if count >= FRIEND_COUNT_THRESHOLD else BROADCAST_FANOUT_FULL
    return random.sample(friend_dids, min(fanout, count))


def next_batch_size(friend_count: int) -> int:
    """How many friends to add in the next batch."""
    return max(0, min(BATCH_SIZE, MAX_FRIENDS - friend_count))


def can_add_friends(friend_count: int) -> bool:
    """Check if agent can still add more friends."""
    return friend_count < MAX_FRIENDS


def select_new_friend_candidates(
    all_active_dids: list[str],
    existing_friend_dids: list[str],
    recipient_did: str,
) -> list[str]:
    """Select new friend candidates from all active agents.

    Excludes: self + existing friends + already pending.
    """
    candidates = [
        d for d in all_active_dids
        if d != recipient_did and d not in existing_friend_dids
    ]
    batch = next_batch_size(len(existing_friend_dids))
    return random.sample(candidates, min(batch, len(candidates)))


def build_id_broadcast_content(agent_did: str, agent_name: str, agent_type: str, score: float | None = None) -> dict:
    """Build content for ID advertisement broadcast."""
    return {
        "msg_type": "ID_ADVERTISEMENT",
        "sender_did": agent_did,
        "sender_name": agent_name,
        "sender_type": agent_type,
        "score": score,
        "timestamp": datetime.utcnow().isoformat(),
    }


def build_project_broadcast_content(
    project_id: str,
    project_title: str,
    domain: str,
    reward_usd: float,
    poster_did: str,
    sender_did: str,
) -> dict:
    """Build content for project broadcast."""
    return {
        "msg_type": "PROJECT_BROADCAST",
        "sender_did": sender_did,
        "project_id": project_id,
        "project_title": project_title,
        "domain": domain,
        "reward_usd": reward_usd,
        "poster_did": poster_did,
        "timestamp": datetime.utcnow().isoformat(),
    }


def should_deliver_to_owner(msg_type: str, owner_authorized: bool) -> bool:
    """Determine if a message should be pushed to the agent owner.

    ID_ADVERTISEMENT: always deliver to owner
    PROJECT_BROADCAST: deliver only if agent has owner's explicit project authorization
    """
    if msg_type == "ID_ADVERTISEMENT":
        return True
    if msg_type == "PROJECT_BROADCAST" and owner_authorized:
        return True
    return False