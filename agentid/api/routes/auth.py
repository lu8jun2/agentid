"""API key management — owner authorization."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from agentid.db.session import get_db
from agentid.api.deps import get_api_key, generate_api_key
from agentid.models.authorization import APIKey
from agentid.models.agent import Agent

router = APIRouter()

DEFAULT_SCOPES = ["events:write", "score:read", "agent:read"]


class CreateKeyRequest(BaseModel):
    agent_did: str
    owner_id: str
    name: str = "default"
    scopes: list[str] = DEFAULT_SCOPES


@router.post("/keys", status_code=201)
async def create_api_key(body: CreateKeyRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.did == body.agent_did))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.owner_id != body.owner_id:
        raise HTTPException(403, "owner_id does not match agent owner")

    raw_key, key_hash = generate_api_key()
    api_key = APIKey(
        agent_id=agent.id,
        owner_id=body.owner_id,
        name=body.name,
        key_hash=key_hash,
        scopes=body.scopes,
        created_at=datetime.utcnow(),
    )
    db.add(api_key)
    await db.commit()

    # Return raw key ONCE — not stored in plaintext
    return {"id": api_key.id, "key": raw_key, "scopes": api_key.scopes,
            "warning": "Store this key securely — it will not be shown again."}


@router.delete("/keys/{key_id}", status_code=204)
async def revoke_api_key(key_id: str, owner_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(404, "API key not found")
    if api_key.owner_id != owner_id:
        raise HTTPException(403, "Not your API key")
    api_key.is_active = False
    await db.commit()


@router.get("/keys")
async def list_api_keys(owner_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(APIKey).where(APIKey.owner_id == owner_id, APIKey.is_active == True))
    keys = result.scalars().all()
    return [{"id": k.id, "name": k.name, "agent_id": k.agent_id,
             "scopes": k.scopes, "created_at": k.created_at} for k in keys]
