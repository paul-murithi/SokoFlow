from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import UUID as PG_UUID
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    shop_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer, CheckConstraint("quantity > 0"), nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        Computed("quantity * unit_price", persisted=True),
    )
    recorded_by: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Composite Index
    __table_args__ = (Index("idx_sales_shop_date", "shop_id", created_at.desc()),)
