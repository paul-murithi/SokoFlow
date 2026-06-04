from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import UUID as PG_UUID
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    shop_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("shops.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_lower: Mapped[str] = mapped_column(
        Text, Computed(func.lower(name), persisted=True), index=True
    )
    sku: Mapped[str] = mapped_column(String(50), unique=True)
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2), CheckConstraint("price >= 0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
