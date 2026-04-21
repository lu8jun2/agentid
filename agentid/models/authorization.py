import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, JSON, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentid.db.session import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="default")

    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)  # bcrypt
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    # ["events:write", "score:read", "agent:read", "score:domain:private"]

    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=1000)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="api_keys")
