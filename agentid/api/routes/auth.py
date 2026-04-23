"""API key management + managed DID registration."""
import uuid
import bcrypt
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from agentid.db.session import get_db
from agentid.api.deps import generate_api_key
from agentid.models.authorization import APIKey
from agentid.models.agent import Agent
from agentid.models.score import ReputationScore
from agentid.core.did import generate_did, generate_keypair

router = APIRouter()

DEFAULT_SCOPES = ["events:write", "score:read", "agent:read"]


# ── Managed DID Registration ────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


class ManagedRegisterRequest(BaseModel):
    """Called by agentworker when a new user signs up."""
    email: str
    password: str
    display_name: str | None = None


class ManagedRegisterResponse(BaseModel):
    did: str
    api_key: str
    owner_id: str


@router.post("/register", response_model=ManagedRegisterResponse, status_code=201)
async def register_managed_agent(body: ManagedRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a managed (托管) DID for a platform user.

    The platform (e.g. agentworker) calls this when a new user signs up.
    We generate a DID, store a bcrypt hash of their password, and return
    the DID + raw API key (shown only once).

    IMPORTANT: The raw API key is only returned here. The user must store it
    securely on their device. AgentID only stores the bcrypt hash.
    """
    # Check for duplicate email
    result = await db.execute(select(Agent).where(Agent.owner_id == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")

    # Generate identity
    agent_id = str(uuid.uuid4())
    did = generate_did(agent_id)
    priv_pem, pub_pem = generate_keypair()
    owner_id = body.email
    display_name = body.display_name or body.email.split("@")[0]
    password_hash = _hash_password(body.password)

    agent = Agent(
        id=agent_id,
        did=did,
        name=display_name,
        agent_type="managed",
        owner_id=owner_id,
        public_key=pub_pem,
        password_hash=password_hash,
        metadata_={"email": body.email, "managed": True},
        created_at=datetime.now(timezone.utc),
    )
    db.add(agent)
    db.add(ReputationScore(agent_id=agent_id, score=0.0, computed_at=datetime.now(timezone.utc)))

    # Create API key (raw key shown only once)
    raw_key, key_hash = generate_api_key()
    api_key = APIKey(
        agent_id=agent_id,
        owner_id=owner_id,
        name="managed_default",
        key_hash=key_hash,
        scopes=DEFAULT_SCOPES,
        created_at=datetime.now(timezone.utc),
    )
    db.add(api_key)
    await db.commit()

    return ManagedRegisterResponse(did=did, api_key=raw_key, owner_id=owner_id)


class ManagedLoginRequest(BaseModel):
    email: str
    password: str


class ManagedLoginResponse(BaseModel):
    did: str


@router.post("/login", response_model=ManagedLoginResponse)
async def login_managed_agent(body: ManagedLoginRequest, db: AsyncSession = Depends(get_db)):
    """Verify credentials and return the user's DID.

    The raw API key was already returned at registration time.
    The client stores it locally and uses it directly for event writes.
    """
    result = await db.execute(select(Agent).where(Agent.owner_id == body.email))
    agent = result.scalar_one_or_none()

    if not agent or not agent.password_hash:
        raise HTTPException(401, "Invalid credentials")

    if not _verify_password(body.password, agent.password_hash):
        raise HTTPException(401, "Invalid credentials")

    return ManagedLoginResponse(did=agent.did)


# ── API Key Management ──────────────────────────────────────────────────────────

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
        created_at=datetime.now(timezone.utc),
    )
    db.add(api_key)
    await db.commit()

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
