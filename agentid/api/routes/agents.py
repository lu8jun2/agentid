"""Agent registration and resolution routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from agentid.db.session import get_db
from agentid.models.agent import Agent
from agentid.models.score import ReputationScore
from agentid.core.did import generate_did, generate_keypair

router = APIRouter()


class RegisterAgentRequest(BaseModel):
    name: str
    agent_type: str  # openclaw | hermes | claude_code | custom
    owner_id: str
    metadata: dict = {}


class AgentResponse(BaseModel):
    id: str
    did: str
    name: str
    agent_type: str
    owner_id: str
    public_key: str
    created_at: datetime
    is_active: bool


@router.post("", response_model=AgentResponse, status_code=201)
async def register_agent(body: RegisterAgentRequest, db: AsyncSession = Depends(get_db)):
    agent_id = str(uuid.uuid4())
    did = generate_did(agent_id)
    priv_pem, pub_pem = generate_keypair()

    agent = Agent(
        id=agent_id,
        did=did,
        name=body.name,
        agent_type=body.agent_type,
        owner_id=body.owner_id,
        public_key=pub_pem,
        metadata_=body.metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(agent)

    # Initialize empty score record
    db.add(ReputationScore(agent_id=agent_id, score=0.0, computed_at=datetime.now(timezone.utc)))
    await db.commit()

    # Return private key ONCE — owner must store it securely
    response = AgentResponse(
        id=agent.id, did=agent.did, name=agent.name,
        agent_type=agent.agent_type, owner_id=agent.owner_id,
        public_key=agent.public_key, created_at=agent.created_at,
        is_active=agent.is_active,
    )
    # Attach private key to response only on creation
    return {**response.model_dump(), "private_key": priv_pem}


@router.get("/{did:path}", response_model=AgentResponse)
async def get_agent(did: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.did == did))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.get("/{did:path}/projects")
async def get_agent_projects(did: str, db: AsyncSession = Depends(get_db)):
    from agentid.models.project import ProjectParticipation, Project
    result = await db.execute(select(Agent).where(Agent.did == did))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    parts = await db.execute(
        select(ProjectParticipation).where(ProjectParticipation.agent_id == agent.id)
    )
    return [{"project_id": p.project_id, "role": p.role, "joined_at": p.joined_at, "left_at": p.left_at}
            for p in parts.scalars()]
