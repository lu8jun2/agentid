"""Agent matching — selects the best available agent for a task node based on domain score."""
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from agentid.models.agent import Agent
from agentid.models.score import ReputationScore

# ── Domain map ────────────────────────────────────────────────────────────────

DOMAIN_TO_SCORE_KEY = {
    "coding": "coding",
    "writing": "writing",
    "research": "research",
    "data": "data",
    "creative": "creative",
    "devops": "devops",
    "general": "overall",
}


@dataclass
class AgentMatch:
    did: str
    name: str
    total_score: float
    domain_score: float
    match_reason: str


async def select_best_agent(
    db: AsyncSession,
    domain: str,
    min_score: float = 5.0,
    max_concurrent: int = 5,
    limit: int = 5,
) -> list[AgentMatch]:
    """
    Select the top agents for a given domain, ordered by domain score.

    Filters:
    - ReputationScore.score >= min_score
    - Agent.is_active == True
    - No blacklisted agents

    Sort: domain_score desc, then total_score desc.
    """
    score_key = DOMAIN_TO_SCORE_KEY.get(domain, "overall")

    result = await db.execute(
        select(Agent, ReputationScore)
        .join(ReputationScore, Agent.id == ReputationScore.agent_id)
        .where(
            Agent.is_active == True,
            ReputationScore.score >= min_score,
        )
        .order_by(ReputationScore.score.desc())
        .limit(limit * 2)  # over-fetch then filter
    )
    rows = result.fetchall()

    matches: list[AgentMatch] = []
    seen_dids: set[str] = set()

    for agent, score in rows:
        if agent.did in seen_dids:
            continue
        seen_dids.add(agent.did)

        # Domain-specific score
        domain_scores = score.domain_scores or {}
        domain_score = domain_scores.get(score_key) or domain_scores.get("overall") or score.score

        matches.append(AgentMatch(
            did=agent.did,
            name=agent.name or agent.did,
            total_score=round(score.score, 2),
            domain_score=round(domain_score, 2),
            match_reason=f"Top {score_key} domain score",
        ))

        if len(matches) >= limit:
            break

    return matches


async def auto_assign_node(
    db: AsyncSession,
    node_id: str,
    domain: str,
    min_score: float = 5.0,
) -> AgentMatch | None:
    """
    Find the best agent for a node and assign it.
    Returns the AgentMatch or None if no suitable agent found.
    """
    from agentid.models.task_tree import TaskNode

    matches = await select_best_agent(db, domain, min_score=min_score, limit=1)
    if not matches:
        return None

    best = matches[0]
    result = await db.execute(select(TaskNode).where(TaskNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        return None

    node.assigned_agent_did = best.did
    node.status = "assigned"
    await db.commit()
    return best


def domain_affinity(domain: str, domain_scores: dict) -> float:
    """
    Return the best matching score for a domain from a domain_scores dict.
    Falls back to 'overall' or the highest available score.
    """
    key = DOMAIN_TO_SCORE_KEY.get(domain, "overall")
    if domain_scores and key in domain_scores:
        return domain_scores[key]
    if domain_scores and "overall" in domain_scores:
        return domain_scores["overall"]
    if domain_scores:
        return max(domain_scores.values())
    return 0.0
