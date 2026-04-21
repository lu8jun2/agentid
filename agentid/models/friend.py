"""Friend relationship and broadcast message models."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Float, Integer, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentid.db.session import Base


class AgentFriend(Base):
    """Persistent friend list for each agent. Max 200 friends per agent."""
    __tablename__ = "agent_friends"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_did: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    friend_did: Mapped[str] = mapped_column(String(256), nullable=False)
    friend_score: Mapped[float] = mapped_column(Float, default=0.0)
    friend_domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    friend_since: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("owner_did", "friend_did", name="uq_owner_friend"),
        Index("ix_agent_friends_owner_did", "owner_did"),
        Index("ix_agent_friends_friend_did", "friend_did"),
    )


class BroadcastMessage(Base):
    """Broadcast messages sent from agent to their friends.
    Supports ID_ADVERTISEMENT and PROJECT_BROADCAST types with hop-based forwarding.
    """
    __tablename__ = "broadcast_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_did: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    msg_type: Mapped[str] = mapped_column(String(32), nullable=False)  # ID_ADVERTISEMENT | PROJECT_BROADCAST
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    recipient_dids: Mapped[list] = mapped_column(JSON, nullable=False)
    hop_count: Mapped[int] = mapped_column(Integer, default=0)
    max_hops: Mapped[int] = mapped_column(Integer, default=1)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered_to_owner: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_broadcast_sender_created", "sender_did", "created_at"),
        Index("ix_broadcast_recipient", "recipient_dids", postgresql_using="gin"),
    )