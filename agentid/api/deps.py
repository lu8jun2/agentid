"""Shared dependencies for FastAPI routes."""
import hashlib
import secrets
from datetime import datetime
from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt

from agentid.db.session import get_db
from agentid.models.authorization import APIKey
from agentid.models.agent import Agent


def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key(prefix: str = "aid_key_") -> tuple[str, str]:
    """Returns (raw_key, key_hash). Store only the hash."""
    raw = prefix + secrets.token_urlsafe(32)
    return raw, _hash_api_key(raw)


async def get_api_key(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    raw_key = authorization.removeprefix("Bearer ").strip()
    key_hash = _hash_api_key(raw_key)

    result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(401, "Invalid or revoked API key")
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(401, "API key expired")

    # Update last_used_at
    api_key.last_used_at = datetime.utcnow()
    await db.commit()
    return api_key


async def require_scope(scope: str, api_key: APIKey = Depends(get_api_key)):
    if scope not in (api_key.scopes or []):
        raise HTTPException(403, f"Missing required scope: {scope}")
    return api_key
