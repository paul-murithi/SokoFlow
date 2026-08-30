from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.sales import DailySummaryResponse
from app.services.report_service import ReportService

router = APIRouter()
service = ReportService()


@router.get("/daily/{shop_id}", response_model=DailySummaryResponse)
async def get_daily_report(
    shop_id: UUID,
    date_: date | None = Query(None, description="ISO-8601 date string (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> DailySummaryResponse:
    target_date = date_ if date_ else date.today()

    return await service.get_daily_report_data(shop_id, target_date, db)
