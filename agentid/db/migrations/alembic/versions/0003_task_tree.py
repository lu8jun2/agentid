"""TaskTree and TaskNode tables.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_trees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("root_node_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, default="planning", index=True),
        sa.Column("total_reward", sa.Float(), nullable=False, default=0.0),
        sa.Column("depth", sa.Integer(), nullable=False, default=0),
        sa.Column("node_count", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "task_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tree_id", sa.String(36), sa.ForeignKey("task_trees.id"), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(64), nullable=False, index=True),
        sa.Column("parent_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("child_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, default="pending", index=True),
        sa.Column("assigned_agent_did", sa.String(256), nullable=True, index=True),
        sa.Column("reward_fraction", sa.Float(), nullable=False, default=0.0),
        sa.Column("estimated_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, default=0),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("delivery_url", sa.String(512), nullable=True),
        sa.Column("failure_reason", sa.String(512), nullable=True),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_task_nodes_tree_status", "task_nodes", ["tree_id", "status"])
    op.create_index("ix_task_trees_client_status", "task_trees", ["client_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_task_trees_client_status")
    op.drop_index("ix_task_nodes_tree_status")
    op.drop_table("task_nodes")
    op.drop_table("task_trees")
