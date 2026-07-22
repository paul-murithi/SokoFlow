from datetime import datetime
from uuid import UUID

from sqlalchemy import UUID as PG_UUID
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("product_id"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("quantity >= 0"),
        nullable=False,
        server_default=text("0"),
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("low_stock_threshold >= 0 AND low_stock_threshold <= 1000"),
        nullable=False,
        server_default=text("5"),
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
