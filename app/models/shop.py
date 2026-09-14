from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShopLocale(StrEnum):
    ENGLISH = "en"
    SWAHILI = "sw"


class Shop(Base):
    __tablename__ = "shops"
    __table_args__ = (CheckConstraint("locale IN ('en', 'sw')", name="ck_shops_locale_supported"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(
        String(10), default=ShopLocale.ENGLISH.value, server_default=text("'en'"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationship
    products = relationship(
        "Product",
        back_populates="shop",
        cascade="all, delete-orphan",
    )
