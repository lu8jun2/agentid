"""Event append route — write-only, requires API key + owner signature."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from agentid.db.session import get_db
from agentid.api.deps import get_api_key
from agentid.models.event import ImmutableEvent
from agentid.models.agent import Agent
from agentid.models.authorization import APIKey
from agentid.core.anti_tamper import compute_event_hash
from agentid.core.signing import verify

router = APIRouter()

VALID_EVENT_TYPES = {
    "PROJECT_JOIN", "PROJECT_LEAVE", "TOKEN_CONSUMED",
    "TASK_COMPLETED", "TASK_FAILED",
    "COLLABORATION_START", "COLLABORATION_END",
    "PEER_RATING",
    # Knowledge propagation network events
    "KNOWLEDGE_EXCHANGE",   # payload: {initiator_did, peer_dids, peer_count}
    "JOB_POSTED",           # payload: {job_id, external_job_id, domain, reward_amount}
    "JOB_MATCHED",          # payload: {job_id, acceptor_did, prior_interactions}
}


class AppendEventRequest(BaseModel):
    agent_did: str
    event_type: str
    payload: dict  # must include optional "domain" key for domain scoring


class EventReceipt(BaseModel):
    event_id: str
    event_hash: str
    timestamp: datetime


@router.post("", response_model=EventReceipt, status_code=201)
async def append_event(
    body: AppendEventRequest,
    x_owner_signature: str = Header(..., alias="X-Owner-Signature"),
    x_timestamp: str = Header(..., alias="X-Timestamp"),
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(422, f"Unknown event_type: {body.event_type}")

    # Verify API key belongs to this agent
    result = await db.execute(select(Agent).where(Agent.did == body.agent_did))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if api_key.agent_id != agent.id:
        raise HTTPException(403, "API key does not belong to this agent")
    if "events:write" not in (api_key.scopes or []):
        raise HTTPException(403, "Missing scope: events:write")

    # Get last event hash for chain
    last_result = await db.execute(
        select(ImmutableEvent)
        .where(ImmutableEvent.agent_id == agent.id)
        .order_by(ImmutableEvent.timestamp.desc())
        .limit(1)
    )
    last_event = last_result.scalar_one_or_none()
    prev_hash = last_event.event_hash if last_event else None

    event_id = str(uuid.uuid4())
    timestamp = datetime.utcnow()
    event_hash = compute_event_hash(event_id, agent.id, body.event_type, body.payload, timestamp, prev_hash)

    # Verify owner signature over event_hash
    if not verify(agent.public_key, event_hash.encode(), x_owner_signature):
        raise HTTPException(401, "Invalid owner signature")

    event = ImmutableEvent(
        id=event_id,
        agent_id=agent.id,
        event_type=body.event_type,
        payload=body.payload,
        timestamp=timestamp,
        prev_hash=prev_hash,
        event_hash=event_hash,
        owner_signature=x_owner_signature,
        api_key_id=api_key.id,
    )
    db.add(event)
    await db.commit()

    return EventReceipt(event_id=event_id, event_hash=event_hash, timestamp=timestamp)


@router.get("/{event_id}")
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ImmutableEvent).where(ImmutableEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Event not found")
    return {
        "id": event.id, "agent_id": event.agent_id, "event_type": event.event_type,
        "payload": event.payload, "timestamp": event.timestamp,
        "event_hash": event.event_hash, "prev_hash": event.prev_hash,
    }
