"""Score recalculation worker — APScheduler backed, runs on a schedule."""
import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, func
from agentid.db.session import AsyncSessionLocal
from agentid.models.agent import Agent
from agentid.models.event import ImmutableEvent
from agentid.models.score import ReputationScore, ScoreSnapshot
from agentid.core.scoring import ScoreInput, compute_score
from agentid.config import settings

log = logging.getLogger("worker.scheduler")

_scheduler: AsyncIOScheduler | None = None

PRACTICE_TASK_WEIGHT = 0.25


def _task_event_weight(payload: dict) -> float:
    return PRACTICE_TASK_WEIGHT if payload.get("task_kind") == "practice" else 1.0


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def recalculate_all_scores():
    log.info("Starting score recalculation...")
    async with AsyncSessionLocal() as db:
        agents_result = await db.execute(select(Agent).where(Agent.is_active == True))
        agents = agents_result.scalars().all()

        for agent in agents:
            try:
                await _recalculate_agent_score(db, agent)
            except Exception as e:
                log.error(f"Score recalc failed for {agent.did}: {e}")

        await db.commit()
    log.info(f"Score recalculation complete for {len(agents)} agents.")


async def _recalculate_agent_score(db, agent: Agent):
    events_result = await db.execute(
        select(ImmutableEvent).where(ImmutableEvent.agent_id == agent.id)
    )
    events = events_result.scalars().all()

    # Aggregate event data
    project_ids = set()
    active_project_ids = set()
    total_tokens = 0
    tasks_completed = 0.0
    tasks_failed = 0.0
    collab_count = 0
    peer_ratings = []
    domain_events: dict[str, dict] = {}

    for e in events:
        p = e.payload
        domain = p.get("domain", "")

        if e.event_type == "PROJECT_JOIN":
            project_ids.add(p.get("project_id", ""))
            active_project_ids.add(p.get("project_id", ""))
        elif e.event_type == "PROJECT_LEAVE":
            active_project_ids.discard(p.get("project_id", ""))
        elif e.event_type == "TOKEN_CONSUMED":
            total_tokens += p.get("tokens", 0)
            if domain:
                domain_events.setdefault(domain, {"tasks": 0, "tokens": 0, "peer_ratings": []})
                domain_events[domain]["tokens"] += p.get("tokens", 0)
        elif e.event_type == "TASK_COMPLETED":
            weight = _task_event_weight(p)
            tasks_completed += weight
            if domain:
                domain_events.setdefault(domain, {"tasks": 0, "tokens": 0, "peer_ratings": []})
                domain_events[domain]["tasks"] += weight
        elif e.event_type == "TASK_FAILED":
            tasks_failed += _task_event_weight(p)
        elif e.event_type in ("COLLABORATION_START",):
            collab_count += 1
        elif e.event_type == "PEER_RATING":
            # Only count ratings targeting this agent
            if p.get("target_did") == agent.did:
                weight = _task_event_weight(p)
                score_val = float(p.get("score", 0))
                weighted_score = settings.global_score_mean + (score_val - settings.global_score_mean) * weight
                peer_ratings.append(weighted_score)
                if domain:
                    domain_events.setdefault(domain, {"tasks": 0, "tokens": 0, "peer_ratings": []})
                    domain_events[domain]["peer_ratings"].append(weighted_score)

    age_days = (datetime.utcnow() - agent.created_at).days

    inp = ScoreInput(
        project_count=len(project_ids),
        active_projects=len(active_project_ids),
        total_tokens=total_tokens,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        collaboration_count=collab_count,
        account_age_days=age_days,
        peer_ratings=peer_ratings,
        domain_events=domain_events,
    )
    result = compute_score(inp)

    # Update or create score record
    score_result = await db.execute(select(ReputationScore).where(ReputationScore.agent_id == agent.id))
    score_rec = score_result.scalar_one_or_none()
    if score_rec:
        score_rec.score = result["score"]
        score_rec.computed_at = datetime.utcnow()
        score_rec.project_count_score = result["components"]["project_count_score"]
        score_rec.survival_rate_score = result["components"]["survival_rate_score"]
        score_rec.token_efficiency_score = result["components"]["token_efficiency_score"]
        score_rec.collaboration_score = result["components"]["collaboration_score"]
        score_rec.longevity_score = result["components"]["longevity_score"]
        score_rec.peer_rating_score = result["components"]["peer_rating_score"]
        score_rec.domain_scores = result["domain_scores"]
    else:
        db.add(ReputationScore(agent_id=agent.id, score=result["score"],
                               computed_at=datetime.utcnow(), **result["components"],
                               domain_scores=result["domain_scores"]))

    # Append snapshot for trend display
    db.add(ScoreSnapshot(agent_id=agent.id, score=result["score"],
                         snapshot_data=result, created_at=datetime.utcnow()))


def start_scheduler():
    """Start the APScheduler background scheduler with score recalc every hour."""
    sched = get_scheduler()
    if not sched.running:
        sched.add_job(
            recalculate_all_scores,
            trigger=IntervalTrigger(minutes=settings.score_recalc_interval_minutes),
            id="recalculate_all_scores",
            replace_existing=True,
        )
        # KNOWLEDGE_EXCHANGE: run every 6 hours
        sched.add_job(
            run_knowledge_exchange,
            trigger=IntervalTrigger(hours=6),
            id="knowledge_exchange",
            replace_existing=True,
        )
        sched.start()
        log.info(f"Scheduler started — score every {settings.score_recalc_interval_minutes}min, exchange every 6h")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
        log.info("Scheduler stopped")


async def run_knowledge_exchange():
    """Randomly pair active agents for knowledge exchange sessions."""
    from agentid.core.network import build_exchange_pairs, build_exchange_package_content

    log.info("Starting KNOWLEDGE_EXCHANGE session...")
    async with AsyncSessionLocal() as db:
        agents_result = await db.execute(select(Agent).where(Agent.is_active == True))
        all_dids = [a.did for a in agents_result.scalars().all()]

        if len(all_dids) < 7:
            log.info(f"Not enough agents ({len(all_dids)}) for KNOWLEDGE_EXCHANGE, skipping.")
            return

        pairs = build_exchange_pairs(all_dids)
        log.info(f"KNOWLEDGE_EXCHANGE: {len(pairs)} groups formed")

        for initiator_did, peer_dids in pairs:
            content = build_exchange_package_content(initiator_did, peer_dids)
            log.info(f"  Group: {initiator_did[:20]}... → {len(peer_dids)} peers")
            # Sessions are recorded in KnowledgeSession table by the dispatch endpoint
            # The scheduler just logs — actual dispatch is triggered by agent polling

        log.info(f"KNOWLEDGE_EXCHANGE session complete: {len(pairs)} groups")


async def run_once():
    """Run one recalculation immediately (CLI entry point)."""
    await recalculate_all_scores()
