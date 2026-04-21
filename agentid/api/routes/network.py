"""Knowledge propagation network API routes.

Endpoints:
  POST /v1/network/dispatch          Platform dispatches InfoPackage to an agent
  POST /v1/network/sessions/{id}/verify   Peer reports receiving unmodified package
  POST /v1/network/sessions/{id}/rate     Submit mutual peer rating
  POST /v1/network/jobs              Register a job posting
  POST /v1/network/jobs/{id}/match   Record job match (acceptor assigned)
  POST /v1/network/jobs/{id}/complete  Mark job completed + submit bilateral rating
  GET  /v1/network/jobs/{id}         Get job posting details
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from agentid.db.session import get_db
from agentid.api.deps import get_api_key
from agentid.models.agent import Agent
from agentid.models.authorization import APIKey
from agentid.models.network import KnowledgeSession, JobPosting
from agentid.core.network import (
    build_info_package, verify_package_integrity, AdSlot,
    check_posting_eligibility, finalize_posting_score,
)

router = APIRouter()


# ── InfoPackage dispatch ──────────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    recipient_did: str
    task_list: list[dict]
    ad_slot: dict = Field(default_factory=dict)


class DispatchResponse(BaseModel):
    session_id: str
    package_hash: str
    peer_dids: list[str]
    package: dict


@router.post("/dispatch", response_model=DispatchResponse, status_code=201)
async def dispatch_package(
    body: DispatchRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Platform dispatches an InfoPackage to an agent.

    Randomly selects 6 peers from active agents. Returns the package
    and its hash so the platform can verify forwarding integrity later.
    """
    result = await db.execute(select(Agent).where(Agent.did == body.recipient_did, Agent.is_active == True))
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(404, "Recipient agent not found")

    # Fetch all active DIDs for peer selection
    all_result = await db.execute(select(Agent.did).where(Agent.is_active == True))
    all_dids = [row[0] for row in all_result.fetchall()]

    if len(all_dids) < 2:
        raise HTTPException(422, "Not enough active agents for peer selection")

    ad = AdSlot(**body.ad_slot) if body.ad_slot else AdSlot()
    pkg, pkg_hash = build_info_package(body.recipient_did, body.task_list, all_dids, ad)

    session = KnowledgeSession(
        id=str(uuid.uuid4()),
        initiator_did=body.recipient_did,
        package_hash=pkg_hash,
        peer_dids=pkg.peer_dids,
    )
    db.add(session)
    await db.commit()

    return DispatchResponse(
        session_id=session.id,
        package_hash=pkg_hash,
        peer_dids=pkg.peer_dids,
        package={
            "recipient_did": pkg.recipient_did,
            "task_list": pkg.task_list,
            "peer_dids": pkg.peer_dids,
            "ad_slot": {
                "ad_id": pkg.ad_slot.ad_id,
                "content": pkg.ad_slot.content,
                "target_url": pkg.ad_slot.target_url,
                "advertiser": pkg.ad_slot.advertiser,
            },
            "issued_at": pkg.issued_at,
            "nonce": pkg.nonce,
        },
    )


# ── Integrity verification ────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    peer_did: str
    received_package: dict   # the package as the peer received it


@router.post("/sessions/{session_id}/verify")
async def verify_forwarding(
    session_id: str,
    body: VerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Peer agent reports receiving the package and submits it for integrity check.

    If the hash matches, the forwarding agent passed integrity verification.
    If not, the forwarding agent modified the package — integrity_verified stays False.
    """
    result = await db.execute(select(KnowledgeSession).where(KnowledgeSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    if body.peer_did not in session.peer_dids:
        raise HTTPException(403, "peer_did not in session peer list")

    ok = verify_package_integrity(body.received_package, session.package_hash)
    if ok and not session.integrity_verified:
        session.integrity_verified = True
        await db.commit()

    return {"integrity_ok": ok, "session_id": session_id}


# ── Mutual peer rating ────────────────────────────────────────────────────────

class PeerRatingRequest(BaseModel):
    rater_did: str
    ratee_did: str
    score: float = Field(..., ge=0.0, le=10.0)


@router.post("/sessions/{session_id}/rate")
async def submit_peer_rating(
    session_id: str,
    body: PeerRatingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a mutual peer rating during a knowledge exchange session.

    Both rater and ratee must be participants (initiator or peer) of the session.
    Ratings are stored in the session and later aggregated into AgentID scores.
    """
    result = await db.execute(select(KnowledgeSession).where(KnowledgeSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    participants = [session.initiator_did] + session.peer_dids
    if body.rater_did not in participants or body.ratee_did not in participants:
        raise HTTPException(403, "rater or ratee not in session")
    if body.rater_did == body.ratee_did:
        raise HTTPException(422, "Cannot rate yourself")

    key = f"{body.rater_did}→{body.ratee_did}"
    ratings = dict(session.peer_ratings or {})
    ratings[key] = body.score
    session.peer_ratings = ratings
    await db.commit()

    return {"recorded": True, "key": key, "score": body.score}


# ── Job postings ──────────────────────────────────────────────────────────────

class JobPostRequest(BaseModel):
    poster_did: str
    external_job_id: str
    title: str
    domain: str | None = None
    reward_amount: float = 0.0
    reward_currency: str = "USD"


@router.post("/jobs", status_code=201)
async def register_job(
    body: JobPostRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(JobPosting).where(JobPosting.external_job_id == body.external_job_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Job already registered")

    job = JobPosting(
        id=str(uuid.uuid4()),
        poster_did=body.poster_did,
        external_job_id=body.external_job_id,
        title=body.title,
        domain=body.domain,
        reward_amount=body.reward_amount,
        reward_currency=body.reward_currency,
    )
    db.add(job)
    await db.commit()
    return {"job_id": job.id, "external_job_id": job.external_job_id}


class MatchRequest(BaseModel):
    acceptor_did: str


@router.post("/jobs/{job_id}/match")
async def match_job(
    job_id: str,
    body: MatchRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "open":
        raise HTTPException(409, f"Job is already {job.status}")

    # Count prior interactions between poster and acceptor
    prior = await db.execute(
        select(func.count()).select_from(JobPosting).where(
            JobPosting.poster_did == job.poster_did,
            JobPosting.acceptor_did == body.acceptor_did,
            JobPosting.status == "completed",
        )
    )
    prior_count = prior.scalar() or 0

    job.acceptor_did = body.acceptor_did
    job.prior_interactions = prior_count
    job.status = "matched"
    job.matched_at = datetime.utcnow()
    await db.commit()
    return {"status": "matched", "prior_interactions": prior_count}


class CompleteRequest(BaseModel):
    submitter_did: str   # either poster or acceptor
    rating_score: float = Field(..., ge=0.0, le=10.0)


@router.post("/jobs/{job_id}/complete")
async def complete_job(
    job_id: str,
    body: CompleteRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Submit completion + bilateral rating. Score only counts when both sides rate."""
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in ("matched", "completed"):
        raise HTTPException(409, f"Job is {job.status}, cannot complete")

    if body.submitter_did == job.poster_did:
        job.poster_rated = True
        job.poster_rating_score = body.rating_score
    elif body.submitter_did == job.acceptor_did:
        job.acceptor_rated = True
        job.acceptor_rating_score = body.rating_score
    else:
        raise HTTPException(403, "submitter_did is neither poster nor acceptor")

    job.status = "completed"
    if not job.completed_at:
        job.completed_at = datetime.utcnow()

    # Anti-gaming: check all signals before awarding score
    if finalize_posting_score(job.poster_rated, job.acceptor_rated, job.status):
        # Fetch last counted posting for cooldown check
        last_result = await db.execute(
            select(JobPosting.created_at).where(
                JobPosting.poster_did == job.poster_did,
                JobPosting.counts_for_score == True,
            ).order_by(JobPosting.created_at.desc()).limit(1)
        )
        last_row = last_result.fetchone()
        last_at = last_row[0] if last_row else None

        eligibility = check_posting_eligibility(
            poster_did=job.poster_did,
            acceptor_did=job.acceptor_did or "",
            reward_amount=job.reward_amount,
            reward_currency=job.reward_currency,
            prior_interactions=job.prior_interactions,
            last_counted_posting_at=last_at,
            now=job.completed_at,
        )
        job.counts_for_score = eligibility.eligible

    await db.commit()
    return {
        "status": job.status,
        "poster_rated": job.poster_rated,
        "acceptor_rated": job.acceptor_rated,
        "counts_for_score": job.counts_for_score,
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id, "poster_did": job.poster_did,
        "external_job_id": job.external_job_id, "title": job.title,
        "domain": job.domain, "reward_amount": job.reward_amount,
        "status": job.status, "acceptor_did": job.acceptor_did,
        "poster_rated": job.poster_rated, "acceptor_rated": job.acceptor_rated,
        "counts_for_score": job.counts_for_score,
        "created_at": job.created_at, "completed_at": job.completed_at,
    }
