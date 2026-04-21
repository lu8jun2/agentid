import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentid.db.session import Base


class ImmutableEvent(Base):
    __tablename__ = "events"
    # DB-level immutability enforced via PostgreSQL rules (see migration)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # PROJECT_JOIN | PROJECT_LEAVE | TOKEN_CONSUMED | TASK_COMPLETED |
    # TASK_FAILED | COLLABORATION_START | COLLABORATION_END | PEER_RATING

    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    # payload always includes optional "domain" key for domain scoring
    # e.g. {"task_id": "t1", "duration_ms": 3000, "domain": "coding"}

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Tamper-evident chain
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # SHA-256(id + agent_id + event_type + payload_json_sorted + timestamp_iso + prev_hash)

    # Owner authorization proof — every write must be signed by the agent owner
    owner_signature: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"), nullable=False)

    agent: Mapped["Agent"] = relationship(back_populates="events")
