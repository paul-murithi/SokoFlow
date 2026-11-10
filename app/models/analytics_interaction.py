from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalyticsInteraction(Base):
    __tablename__ = "analytics_interactions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shop_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(64))
    tool_name: Mapped[str | None] = mapped_column(String(100))
    selected_arguments: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(150))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    repair_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    actual_cost: Mapped[float | None] = mapped_column(Float)
    usage_status: Mapped[str] = mapped_column(String(24), nullable=False)
    guardrail_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    guardrail_reason: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
