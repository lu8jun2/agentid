import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentid.db.session import Base


class ReputationScore(Base):
    __tablename__ = "reputation_scores"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 - 10.0
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Component breakdown (transparent scoring)
    project_count_score: Mapped[float] = mapped_column(Float, default=0.0)
    survival_rate_score: Mapped[float] = mapped_column(Float, default=0.0)
    token_efficiency_score: Mapped[float] = mapped_column(Float, default=0.0)
    collaboration_score: Mapped[float] = mapped_column(Float, default=0.0)
    longevity_score: Mapped[float] = mapped_column(Float, default=0.0)
    peer_rating_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Domain-specific scores: {"coding": 8.2, "writing": 7.1, ...}
    domain_scores: Mapped[dict] = mapped_column(JSON, default=dict)

    agent: Mapped["Agent"] = relationship(back_populates="score")


class ScoreSnapshot(Base):
    """Append-only history of score changes for trend display."""
    __tablename__ = "score_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    snapshot_data: Mapped[dict] = mapped_column(JSON)  # full component breakdown
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
