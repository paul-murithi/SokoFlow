import logging
from datetime import date
from uuid import UUID

from app.core.database import get_worker_db
from app.fsm.models import ReportPayload
from app.schemas.sales import DailySummaryResponse
from app.services.pdf_service import PDFReportService
from app.services.report_service import ReportService
from app.workers.async_runtime import run
from app.workers.message_sender import MessageDeliveryError, build_message_sender
from celery_app.celery import celery

logger = logging.getLogger(__name__)
report_service = ReportService()
pdf_service = PDFReportService()
MESSAGE_SENDER = build_message_sender()


@celery.task
def report_task(payload: dict[str, object]) -> None:
    """Celery task to generate a daily report PDF asynchronously and deliver it as a
    document message."""
    inbound_payload = ReportPayload.model_validate(payload)
    shop_id = inbound_payload.shop_id
    recipient = inbound_payload.recipient
    target_date = inbound_payload.date_str or date.today()

    logger.info(
        f"Triggered report_task for shop_id={shop_id}, recipient={recipient}, date={target_date}"
    )
    return run(process_report(shop_id, recipient, target_date))


async def process_report(shop_id: UUID, recipient: str, target_date: date) -> None:
    report_data = await _get_daily_summary_data(shop_id, target_date)
    pdf_bytes = pdf_service.generate_daily_summary_pdf(
        summary=report_data,
        report_date=target_date,
    )

    filename = f"daily_report_{target_date.strftime('%Y_%m_%d')}.pdf"

    try:
        MESSAGE_SENDER.send_document(
            recipient=recipient,
            document_bytes=pdf_bytes,
            filename=filename,
            caption=f"Daily Sales Report for {target_date.strftime('%B %d, %Y')}",
        )
    except MessageDeliveryError:
        logger.exception("An error occurred while delivering report document message")


async def _get_daily_summary_data(shop_id: UUID, target_date: date) -> DailySummaryResponse:
    async with get_worker_db() as db_session:
        return await report_service.get_daily_report_data(
            shop_id=shop_id,
            date=target_date,
            db=db_session,
        )
