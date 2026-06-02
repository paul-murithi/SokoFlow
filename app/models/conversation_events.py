from datetime import datetime
from enum import Enum
from uuid import UUID
from typing import Any

from sqlalchemy import String, TIMESTAMP, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.core.database import Base


class Direction(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ConversationEvents(Base):
    __tablename__ = "conversation_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    correlation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )

    phone: Mapped[str] = mapped_column(String(20), nullable=False)

    direction: Mapped[Direction] = mapped_column(
        SQLEnum(Direction, name="direction_enum"), nullable=False
    )

    message_id: Mapped[str | None] = mapped_column(String(100), unique=True)

    fsm_state_from: Mapped[str | None] = mapped_column(String(50))

    fsm_state_to: Mapped[str | None] = mapped_column(String(50))

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
