"""create analytics interactions table

Revision ID: f0a1b2c3d4e5
Revises: 8a9f1d7c7c4b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "b54f7a1d8e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shop_ref", sa.String(length=64), nullable=False),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("failure_category", sa.String(length=64)),
        sa.Column("tool_name", sa.String(length=100)),
        sa.Column("selected_arguments", postgresql.JSONB()),
        sa.Column("provider", sa.String(length=100)),
        sa.Column("model", sa.String(length=150)),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("repair_count", sa.Integer(), nullable=False),
        sa.Column("total_latency_ms", sa.Float(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Float()),
        sa.Column("actual_cost", sa.Float()),
        sa.Column("usage_status", sa.String(length=24), nullable=False),
        sa.Column("guardrail_decision", sa.String(length=16), nullable=False),
        sa.Column("guardrail_reason", sa.String(length=64)),
        sa.Column("attempts", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_analytics_interactions_shop_ref", "analytics_interactions", ["shop_ref"])


def downgrade() -> None:
    op.drop_index("ix_analytics_interactions_shop_ref", table_name="analytics_interactions")
    op.drop_table("analytics_interactions")
