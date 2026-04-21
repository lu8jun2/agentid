"""Score query and leaderboard routes — all public read."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from agentid.db.session import get_db
from agentid.models.score import ReputationScore
from agentid.models.agent import Agent
from agentid.core.anti_tamper import verify_chain
from agentid.models.event import ImmutableEvent

router = APIRouter()


@router.get("/leaderboard")
async def leaderboard(limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ReputationScore, Agent.name, Agent.did, Agent.agent_type)
        .join(Agent, Agent.id == ReputationScore.agent_id)
        .where(Agent.is_active == True)
        .order_by(desc(ReputationScore.score))
        .limit(limit)
    )
    rows = result.all()
    return [
        {"rank": i + 1, "did": r.did, "name": r.name, "agent_type": r.agent_type,
         "score": r.ReputationScore.score, "domain_scores": r.ReputationScore.domain_scores}
        for i, r in enumerate(rows)
    ]


@router.get("/leaderboard/{domain}")
async def leaderboard_by_domain(domain: str, limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ReputationScore, Agent.name, Agent.did, Agent.agent_type)
        .join(Agent, Agent.id == ReputationScore.agent_id)
        .where(Agent.is_active == True)
        .order_by(desc(ReputationScore.score))
        .limit(500)  # fetch more, filter in Python
    )
    rows = result.all()
    domain_rows = [
        r for r in rows
        if r.ReputationScore.domain_scores and domain in r.ReputationScore.domain_scores
    ]
    domain_rows.sort(key=lambda r: r.ReputationScore.domain_scores.get(domain, 0), reverse=True)
    return [
        {"rank": i + 1, "did": r.did, "name": r.name, "agent_type": r.agent_type,
         "domain": domain, "domain_score": r.ReputationScore.domain_scores.get(domain, 0)}
        for i, r in enumerate(domain_rows[:limit])
    ]


@router.get("/{did:path}/score")
async def get_score(did: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.did == did))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    score_result = await db.execute(select(ReputationScore).where(ReputationScore.agent_id == agent.id))
    score = score_result.scalar_one_or_none()
    if not score:
        raise HTTPException(404, "Score not computed yet")
    return {
        "did": did, "score": score.score,
        "components": {
            "project_count": score.project_count_score,
            "survival_rate": score.survival_rate_score,
            "token_efficiency": score.token_efficiency_score,
            "collaboration": score.collaboration_score,
            "longevity": score.longevity_score,
            "peer_rating": score.peer_rating_score,
        },
        "domain_scores": score.domain_scores or {},
        "computed_at": score.computed_at,
    }


@router.get("/verify/chain/{did:path}")
async def verify_event_chain(did: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.did == did))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    events_result = await db.execute(
        select(ImmutableEvent).where(ImmutableEvent.agent_id == agent.id)
    )
    events = events_result.scalars().all()
    is_valid, broken_id = verify_chain(events)
    return {"did": did, "valid": is_valid, "broken_event_id": broken_id, "event_count": len(events)}
