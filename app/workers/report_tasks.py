import logging

from celery_app.celery import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.workers.report_tasks.generate_and_send_daily_report")
def generate_and_send_daily_report(shop_id: str, recipient: str, date_str: str) -> None:
    """
    Celery task to generate a daily report PDF asynchronously and deliver it as a document message.
    """
    """
    TODO:
    1. Fetch daily summary report data for the given shop_id and date.
    2. Generate PDF via PDFReportService within 5 seconds.
    3. Deliver document message via MessageSender
    """
    logger.info(
        f"""
            Triggered generate_and_send_daily_report for shop_id={shop_id},
            recipient={recipient}, date={date_str}
        """
    )
