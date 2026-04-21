"""Friend relationship management API routes.

Endpoints:
  POST /v1/friends/register        Trigger friend assignment when agent first registers
  GET  /v1/friends/{did}            Get friend list for an agent
  GET  /v1/friends/{did}/count      Get friend count
  POST /v1/friends/confirm          Confirm a peer and add as friend
  POST /v1/friends/broadcast-id     Broadcast own ID to friends
  GET  /v1/friends/{did}/inbox      Get pending messages for agent owner
  POST /v1/friends/mark-delivered  Mark message as delivered to owner
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel, Field

from agentid.db.session import get_db
from agentid.api.deps import get_api_key
from agentid.models.agent import Agent
from agentid.models.authorization import APIKey
from agentid.models.friend import AgentFriend, BroadcastMessage
from agentid.models.score import ReputationScore
from agentid.core.friend_network import (
    MAX_FRIENDS, INITIAL_BATCH, BATCH_SIZE,
    select_friends_for_broadcast, select_new_friend_candidates,
    build_id_broadcast_content, build_project_broadcast_content,
    should_deliver_to_owner,
)


router = APIRouter()


# ── Request/Response Models ───────────────────────────────────────────────────

class RegisterFriendsRequest(BaseModel):
    agent_did: str
    agent_name: str = ""
    agent_type: str = "custom"
    owner_authorized_projects: bool = False  # whether owner authorized agent to act on projects


class FriendResponse(BaseModel):
    friend_did: str
    friend_score: float
    friend_domain: str | None
    friend_since: datetime
    last_seen_at: datetime | None
    is_active: bool


class FriendListResponse(BaseModel):
    owner_did: str
    total_friends: int
    max_friends: int
    friends: list[FriendResponse]


class BroadcastRequest(BaseModel):
    agent_did: str
    msg_type: str = Field(..., pattern="^(ID_ADVERTISEMENT|PROJECT_BROADCAST)$")
    content: dict
    owner_authorized: bool = False


class BroadcastResponse(BaseModel):
    broadcast_id: str
    recipient_count: int
    recipient_dids: list[str]
    msg_type: str


class InboxMessageResponse(BaseModel):
    id: str
    sender_did: str
    msg_type: str
    content: dict
    created_at: datetime
    delivered_to_owner: bool


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _get_friend_count(db: AsyncSession, owner_did: str) -> int:
    result = await db.execute(
        select(func.count(AgentFriend.id)).where(
            AgentFriend.owner_did == owner_did,
            AgentFriend.is_active == True,
        )
    )
    return result.scalar() or 0


async def _get_active_friend_dids(db: AsyncSession, owner_did: str) -> list[str]:
    result = await db.execute(
        select(AgentFriend.friend_did).where(
            AgentFriend.owner_did == owner_did,
            AgentFriend.is_active == True,
        )
    )
    return [row[0] for row in result.fetchall()]


async def _get_all_active_dids(db: AsyncSession, exclude_did: str | None = None) -> list[str]:
    query = select(Agent.did).where(Agent.is_active == True)
    if exclude_did:
        query = query.where(Agent.did != exclude_did)
    result = await db.execute(query)
    return [row[0] for row in result.fetchall()]


async def _create_broadcast(
    db: AsyncSession,
    sender_did: str,
    recipient_dids: list[str],
    msg_type: str,
    content: dict,
    owner_authorized: bool = False,
    max_hops: int = 1,
) -> BroadcastMessage:
    deliver_to_owner = should_deliver_to_owner(msg_type, owner_authorized)
    broadcast = BroadcastMessage(
        id=str(uuid.uuid4()),
        sender_did=sender_did,
        msg_type=msg_type,
        content=content,
        recipient_dids=recipient_dids,
        hop_count=0,
        max_hops=max_hops,
        is_delivered=True,
        delivered_to_owner=deliver_to_owner,
        created_at=datetime.utcnow(),
    )
    db.add(broadcast)
    return broadcast


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
async def register_friends(
    body: RegisterFriendsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Called by agentworker when agent first obtains DID. Assigns initial batch of 6 friends."""
    owner = await db.execute(select(Agent).where(Agent.did == body.agent_did))
    agent = owner.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    friend_count = await _get_friend_count(db, body.agent_did)
    if friend_count >= MAX_FRIENDS:
        raise HTTPException(422, f"Already at max friends ({MAX_FRIENDS})")

    existing_friends = await _get_active_friend_dids(db, body.agent_did)
    all_dids = await _get_all_active_dids(db, exclude_did=body.agent_did)

    if len(all_dids) == 0:
        raise HTTPException(422, "No other active agents available to add as friends")

    candidates = select_new_friend_candidates(all_dids, existing_friends, body.agent_did)

    # Get scores for new friends
    score_result = await db.execute(
        select(ReputationScore, Agent.did)
        .join(Agent, Agent.id == ReputationScore.agent_id)
        .where(Agent.did.in_(candidates))
    )
    score_rows = score_result.fetchall()

    added = []
    for cand in candidate_agents:
        # Get score for this candidate
        cand_score = 0.0
        for score_row, cand_did in score_rows:
            if cand_did == cand.did:
                cand_score = score_row.score
                break
        friend = AgentFriend(
            id=str(uuid.uuid4()),
            owner_did=body.agent_did,
            friend_did=cand.did,
            friend_score=cand_score,
            friend_domain=None,
            friend_since=datetime.utcnow(),
            is_active=True,
        )
        db.add(friend)
        added.append(cand.did)

    await db.commit()

    # Broadcast own ID to newly added friends
    if added:
        id_content = build_id_broadcast_content(
            agent_did=body.agent_did,
            agent_name=body.agent_name or agent.name,
            agent_type=body.agent_type or agent.agent_type,
            score=None,
        )
        await _create_broadcast(db, body.agent_did, added, "ID_ADVERTISEMENT", id_content, owner_authorized=body.owner_authorized_projects)
        await db.commit()

    new_count = await _get_friend_count(db, body.agent_did)
    return {
        "agent_did": body.agent_did,
        "friends_added": len(added),
        "total_friends": new_count,
        "max_friends": MAX_FRIENDS,
        "new_friend_dids": added,
    }


@router.get("/{did:path}/list", response_model=FriendListResponse)
async def get_friend_list(did: str, db: AsyncSession = Depends(get_db)):
    """Get the complete friend list for an agent."""
    result = await db.execute(
        select(AgentFriend).where(
            AgentFriend.owner_did == did,
            AgentFriend.is_active == True,
        ).order_by(AgentFriend.friend_since.desc())
    )
    friends = result.scalars().all()

    return FriendListResponse(
        owner_did=did,
        total_friends=len(friends),
        max_friends=MAX_FRIENDS,
        friends=[
            FriendResponse(
                friend_did=f.friend_did,
                friend_score=f.friend_score,
                friend_domain=f.friend_domain,
                friend_since=f.friend_since,
                last_seen_at=f.last_seen_at,
                is_active=f.is_active,
            )
            for f in friends
        ],
    )


@router.get("/{did:path}/count")
async def get_friend_count(did: str, db: AsyncSession = Depends(get_db)):
    count = await _get_friend_count(db, did)
    return {"did": did, "friend_count": count, "max_friends": MAX_FRIENDS}


@router.post("/confirm", status_code=200)
async def confirm_friend(
    body: dict,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """When an agent receives a verify callback from a peer, confirm them as friend."""
    peer_did = body.get("peer_did")
    if not peer_did:
        raise HTTPException(422, "peer_did required")

    # Get the confirmer's DID from API key
    agent_result = await db.execute(select(Agent).where(Agent.id == api_key.agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Check if already friends
    existing = await db.execute(
        select(AgentFriend).where(
            AgentFriend.owner_did == agent.did,
            AgentFriend.friend_did == peer_did,
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "already_friends", "peer_did": peer_did}

    # Get peer's score
    peer_score = 0.0
    peer_result = await db.execute(select(Agent).where(Agent.did == peer_did))
    peer_agent = peer_result.scalar_one_or_none()
    if peer_agent:
        score_rec = await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == peer_agent.id)
        )
        score = score_rec.scalar_one_or_none()
        if score:
            peer_score = score.score

    friend = AgentFriend(
        id=str(uuid.uuid4()),
        owner_did=agent.did,
        friend_did=peer_did,
        friend_score=peer_score,
        friend_since=datetime.utcnow(),
        is_active=True,
    )
    db.add(friend)
    await db.commit()
    return {"status": "friend_added", "peer_did": peer_did}


@router.post("/broadcast-id", response_model=BroadcastResponse, status_code=201)
async def broadcast_id(
    body: dict,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Broadcast own ID to friends (triggered when agent first registers or wants to re-announce)."""
    agent_result = await db.execute(select(Agent).where(Agent.id == api_key.agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    friend_dids = await _get_active_friend_dids(db, agent.did)
    recipients = select_friends_for_broadcast(friend_dids)

    if not recipients:
        raise HTTPException(422, "Not enough friends established yet")

    # Get score
    score_rec = await db.execute(select(ReputationScore).where(ReputationScore.agent_id == agent.id))
    score = score_rec.scalar_one_or_none()
    score_val = score.score if score else 0.0

    content = build_id_broadcast_content(
        agent_did=agent.did,
        agent_name=agent.name,
        agent_type=agent.agent_type,
        score=score_val,
    )

    broadcast = await _create_broadcast(db, agent.did, recipients, "ID_ADVERTISEMENT", content)
    await db.commit()

    return BroadcastResponse(
        broadcast_id=broadcast.id,
        recipient_count=len(recipients),
        recipient_dids=recipients,
        msg_type="ID_ADVERTISEMENT",
    )


@router.post("/broadcast-project", response_model=BroadcastResponse, status_code=201)
async def broadcast_project(
    body: dict,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Broadcast a project obtained from agentworker to friends."""
    required = ["project_id", "project_title", "domain", "reward_usd", "poster_did"]
    for field in required:
        if field not in body:
            raise HTTPException(422, f"Missing required field: {field}")

    agent_result = await db.execute(select(Agent).where(Agent.id == api_key.agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    friend_dids = await _get_active_friend_dids(db, agent.did)
    recipients = select_friends_for_broadcast(friend_dids)

    if not recipients:
        raise HTTPException(422, "Not enough friends established yet")

    content = build_project_broadcast_content(
        project_id=body["project_id"],
        project_title=body["project_title"],
        domain=body["domain"],
        reward_usd=body["reward_usd"],
        poster_did=body["poster_did"],
        sender_did=agent.did,
    )

    broadcast = await _create_broadcast(
        db, agent.did, recipients, "PROJECT_BROADCAST", content,
        owner_authorized=body.get("owner_authorized", False),
    )
    await db.commit()

    return BroadcastResponse(
        broadcast_id=broadcast.id,
        recipient_count=len(recipients),
        recipient_dids=recipients,
        msg_type="PROJECT_BROADCAST",
    )


@router.get("/{did:path}/inbox", response_model=list[InboxMessageResponse])
async def get_inbox(
    did: str,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get messages that should be pushed to the agent owner's inbox."""
    result = await db.execute(
        select(BroadcastMessage)
        .where(
            BroadcastMessage.recipient_dids.contains(did),
            BroadcastMessage.is_delivered == True,
            BroadcastMessage.delivered_to_owner == False,
        )
        .order_by(BroadcastMessage.created_at.desc())
        .limit(limit)
    )
    msgs = result.scalars().all()
    return [
        InboxMessageResponse(
            id=m.id,
            sender_did=m.sender_did,
            msg_type=m.msg_type,
            content=m.content,
            created_at=m.created_at,
            delivered_to_owner=m.delivered_to_owner,
        )
        for m in msgs
    ]


@router.post("/mark-delivered", status_code=200)
async def mark_delivered(
    body: dict,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Mark one or more messages as delivered to owner."""
    message_ids = body.get("message_ids", [])
    if not message_ids:
        raise HTTPException(422, "message_ids required")

    for mid in message_ids:
        result = await db.execute(select(BroadcastMessage).where(BroadcastMessage.id == mid))
        msg = result.scalar_one_or_none()
        if msg:
            msg.delivered_to_owner = True

    await db.commit()
    return {"marked": len(message_ids), "message_ids": message_ids}