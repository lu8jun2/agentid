"""Initial schema with immutable events table.

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # agents table
    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("did", sa.String(256), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(256), nullable=False),
        sa.Column("public_key", sa.Text, nullable=False),
        sa.Column("metadata", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
    )
    op.create_index("ix_agents_did", "agents", ["did"])
    op.create_index("ix_agents_owner_id", "agents", ["owner_id"])

    # api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("owner_id", sa.String(256), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("scopes", postgresql.JSON, nullable=True),
        sa.Column("rate_limit_per_hour", sa.Integer, default=1000),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
    )

    # events table — append-only, PostgreSQL rules enforce immutability
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSON, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("event_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("owner_signature", sa.Text, nullable=False),
        sa.Column("api_key_id", sa.String(36), sa.ForeignKey("api_keys.id"), nullable=False),
    )
    op.create_index("ix_events_agent_id", "events", ["agent_id"])
    op.create_index("ix_events_timestamp", "events", ["timestamp"])

    # PostgreSQL immutability rules — no UPDATE or DELETE on events
    op.execute("CREATE RULE no_update_events AS ON UPDATE TO events DO INSTEAD NOTHING;")
    op.execute("CREATE RULE no_delete_events AS ON DELETE TO events DO INSTEAD NOTHING;")

    # Trigger: enforce prev_hash chain integrity on INSERT
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_event_chain() RETURNS TRIGGER AS $$
        DECLARE last_hash TEXT;
        BEGIN
            SELECT event_hash INTO last_hash
            FROM events WHERE agent_id = NEW.agent_id
            ORDER BY timestamp DESC LIMIT 1;
            IF last_hash IS NOT NULL AND NEW.prev_hash IS DISTINCT FROM last_hash THEN
                RAISE EXCEPTION 'Event chain broken: prev_hash mismatch for agent %', NEW.agent_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER check_event_chain
        BEFORE INSERT ON events
        FOR EACH ROW EXECUTE FUNCTION enforce_event_chain();
    """)

    # projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # project_participations table
    op.create_table(
        "project_participations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("role", sa.String(64), default="participant"),
        sa.Column("joined_at", sa.DateTime, nullable=False),
        sa.Column("left_at", sa.DateTime, nullable=True),
    )

    # reputation_scores table
    op.create_table(
        "reputation_scores",
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), primary_key=True),
        sa.Column("score", sa.Float, nullable=False, default=0.0),
        sa.Column("computed_at", sa.DateTime, nullable=False),
        sa.Column("project_count_score", sa.Float, default=0.0),
        sa.Column("survival_rate_score", sa.Float, default=0.0),
        sa.Column("token_efficiency_score", sa.Float, default=0.0),
        sa.Column("collaboration_score", sa.Float, default=0.0),
        sa.Column("longevity_score", sa.Float, default=0.0),
        sa.Column("peer_rating_score", sa.Float, default=0.0),
        sa.Column("domain_scores", postgresql.JSON, nullable=True),
    )

    # score_snapshots table
    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("snapshot_data", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_score_snapshots_agent_id", "score_snapshots", ["agent_id"])

    # knowledge_sessions table
    op.create_table(
        "knowledge_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("initiator_did", sa.String(256), nullable=False),
        sa.Column("package_hash", sa.String(64), nullable=False),
        sa.Column("peer_dids", postgresql.JSON, nullable=False),
        sa.Column("peer_ratings", postgresql.JSON, nullable=True),
        sa.Column("integrity_verified", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )

    # job_postings table
    op.create_table(
        "job_postings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("poster_did", sa.String(256), nullable=False),
        sa.Column("external_job_id", sa.String(256), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("domain", sa.String(64), nullable=True),
        sa.Column("reward_amount", sa.Float, nullable=False, default=0.0),
        sa.Column("reward_currency", sa.String(16), default="USD"),
        sa.Column("status", sa.String(32), default="open"),
        sa.Column("acceptor_did", sa.String(256), nullable=True),
        sa.Column("poster_rated", sa.Boolean, default=False),
        sa.Column("acceptor_rated", sa.Boolean, default=False),
        sa.Column("poster_rating_score", sa.Float, nullable=True),
        sa.Column("acceptor_rating_score", sa.Float, nullable=True),
        sa.Column("prior_interactions", sa.Integer, default=0),
        sa.Column("counts_for_score", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("matched_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS check_event_chain ON events;")
    op.execute("DROP FUNCTION IF EXISTS enforce_event_chain();")
    op.execute("DROP RULE IF EXISTS no_update_events ON events;")
    op.execute("DROP RULE IF EXISTS no_delete_events ON events;")
    for table in [
        "job_postings",
        "knowledge_sessions",
        "score_snapshots",
        "reputation_scores",
        "project_participations",
        "projects",
        "events",
        "api_keys",
        "agents",
    ]:
        op.drop_table(table, if_exists=True)