"""Friend relationship and broadcast message tables.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_friends",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_did", sa.String(256), nullable=False),
        sa.Column("friend_did", sa.String(256), nullable=False),
        sa.Column("friend_score", sa.Float, default=0.0),
        sa.Column("friend_domain", sa.String(64), nullable=True),
        sa.Column("friend_since", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
    )
    op.create_index("ix_agent_friends_owner_did", "agent_friends", ["owner_did"])
    op.create_index("ix_agent_friends_friend_did", "agent_friends", ["friend_did"])
    op.execute("CREATE UNIQUE INDEX uq_owner_friend ON agent_friends(owner_did, friend_did)")

    op.create_table(
        "broadcast_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sender_did", sa.String(256), nullable=False),
        sa.Column("msg_type", sa.String(32), nullable=False),
        sa.Column("content", postgresql.JSON, nullable=False),
        sa.Column("recipient_dids", postgresql.JSON, nullable=False),
        sa.Column("hop_count", sa.Integer, default=0),
        sa.Column("max_hops", sa.Integer, default=1),
        sa.Column("expired_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("is_delivered", sa.Boolean, default=False),
        sa.Column("delivered_to_owner", sa.Boolean, default=False),
    )
    op.create_index("ix_broadcast_sender_created", "broadcast_messages", ["sender_did", "created_at"])
    op.create_index("ix_broadcast_created", "broadcast_messages", ["created_at"])
    # For recipient_dids GIN index, use PostgreSQL specific syntax
    op.execute("CREATE INDEX ix_broadcast_recipient ON broadcast_messages USING gin(recipient_dids)")


def downgrade() -> None:
    for table in ["broadcast_messages", "agent_friends"]:
        op.drop_table(table, if_exists=True)