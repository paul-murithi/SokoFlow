from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sales_service import SalesService


class ReportService:
    def __init__(self) -> None:
        self.sales_service = SalesService()

    async def get_daily_report_data(
        self, shop_id: UUID, date: date, db: AsyncSession
    ) -> dict[str, Any]:  # TODO: Improve function return type annotation
        return await self.sales_service.get_daily_summary(shop_id, date, db)
