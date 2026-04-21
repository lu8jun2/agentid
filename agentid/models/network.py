"""Models for knowledge propagation network."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, ForeignKey, Integer, Float, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentid.db.session import Base


class KnowledgeSession(Base):
    """Records a single knowledge exchange session between agents.

    Platform dispatches an InfoPackage to agent A; agent A forwards it to
    peers B-G. Each forward is recorded here. Modification = integrity failure.
    """
    __tablename__ = "knowledge_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # The agent that received the info package from the platform
    initiator_did: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    # SHA-256 of the canonical info package — used to verify forwarded content is unmodified
    package_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # DIDs of the 6 randomly paired peer agents
    peer_dids: Mapped[list] = mapped_column(JSON, nullable=False)  # list[str]
    # Mutual ratings submitted during this session: {did: score}
    peer_ratings: Mapped[dict] = mapped_column(JSON, default=dict)
    # Whether all peers confirmed receiving the unmodified package
    integrity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class JobPosting(Base):
    """Tracks job postings published by agents on behalf of their owners.

    Used for job-posting quality scoring with anti-gaming enforcement.
    """
    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    poster_did: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    # External job ID from agentworker or other marketplace
    external_job_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reward_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reward_currency: Mapped[str] = mapped_column(String(16), default="USD")
    status: Mapped[str] = mapped_column(String(32), default="open")
    # open | matched | completed | cancelled

    # Anti-gaming: track who accepted and completed
    acceptor_did: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Bilateral ratings (both sides must rate for score to count)
    poster_rated: Mapped[bool] = mapped_column(Boolean, default=False)
    acceptor_rated: Mapped[bool] = mapped_column(Boolean, default=False)
    poster_rating_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    acceptor_rating_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Anti-gaming: interaction history count between poster and acceptor at time of match
    prior_interactions: Mapped[int] = mapped_column(Integer, default=0)
    # Whether this posting counts toward poster's quality score
    counts_for_score: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    matched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
