import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentid.db.session import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    did: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)  # openclaw|hermes|claude_code|custom
    owner_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)  # Ed25519 PEM
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)  # bcrypt hash for managed DID
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    events: Mapped[list["ImmutableEvent"]] = relationship(back_populates="agent", lazy="select")
    score: Mapped["ReputationScore"] = relationship(back_populates="agent", uselist=False)
    api_keys: Mapped[list["APIKey"]] = relationship(back_populates="agent")
    participations: Mapped[list["ProjectParticipation"]] = relationship(back_populates="agent")
