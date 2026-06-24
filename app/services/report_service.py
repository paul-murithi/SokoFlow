from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sales_service import SalesService


class ReportService:
    def __init__(self) -> None:
        self.sales_service = SalesService()

    async def get_daily_report_data(
        self, shop_id: UUID, date: datetime, db: AsyncSession
    ) -> dict:
        return await self.sales_service.get_daily_summary(shop_id, date, db)
