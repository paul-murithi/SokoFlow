from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.fsm.models import ReportPayload, UserSession
from app.fsm.primitives import FSMPrimitives
from app.workers.queues import QueueName
from app.workers.report_tasks import report_task


class ReportFlow(FSMPrimitives):
    def __init__(self, db_session: AsyncSession | None = None) -> None:
        self.db = db_session

    async def handle_daily_report(self, session: UserSession, message: str) -> None:
        recipient = session.phone

        if session.context.shop_id is not None:
            shop_id = session.context.shop_id
        else:
            async with self._get_db_session(self.db) as db:
                shop_id = await self.get_shop_id(db=db, sender=recipient)
                session.context.shop_id = shop_id

        payload = ReportPayload(
            shop_id=shop_id,
            recipient=recipient,
            date_str=None,
        )

        report_task.apply_async(
            args=(payload.model_dump(mode="json"),),
            queue=QueueName.REPORTS,
        )
