from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.fsm.models import ReportPayload
from app.schemas.sales import DailySummaryResponse
from app.workers import report_tasks
from app.workers.message_sender import MessageDeliveryError


def test_report_task_invocation():
    shop_id = uuid4()
    recipient = "+254700000001"
    payload = ReportPayload(shop_id=shop_id, recipient=recipient, date_str=date(2026, 9, 4))

    with (
        patch("app.workers.report_tasks.run") as mock_run,
        patch("app.workers.report_tasks.process_report") as mock_process,
    ):
        report_tasks.report_task(payload.model_dump(mode="json"))
        mock_run.assert_called_once()
        mock_process.assert_called_once_with(shop_id, recipient, date(2026, 9, 4))


@pytest.mark.asyncio
async def test_process_report_success():
    shop_id = uuid4()
    recipient = "+254700000001"
    target_date = date(2026, 9, 4)
    dummy_summary = DailySummaryResponse(total_revenue=Decimal("500.00"), transaction_count=3)

    mock_sender = MagicMock()

    with (
        patch.object(
            report_tasks.report_service,
            "get_daily_report_data",
            new_callable=AsyncMock,
            return_value=dummy_summary,
        ),
        patch.object(
            report_tasks.pdf_service,
            "generate_daily_summary_pdf",
            return_value=b"%PDF-1.4 dummy pdf bytes",
        ),
        patch.object(
            report_tasks,
            "MESSAGE_SENDER",
            new=mock_sender,
        ),
    ):
        await report_tasks.process_report(shop_id, recipient, target_date)
        mock_sender.send_document.assert_called_once_with(
            recipient=recipient,
            document_bytes=b"%PDF-1.4 dummy pdf bytes",
            filename="daily_report_2026_09_04.pdf",
            caption="Daily Sales Report for September 04, 2026",
        )


@pytest.mark.asyncio
async def test_process_report_handles_delivery_error():
    shop_id = uuid4()
    recipient = "+254700000001"
    target_date = date(2026, 9, 4)
    dummy_summary = DailySummaryResponse(total_revenue=Decimal("100.00"), transaction_count=1)

    mock_sender = MagicMock()
    mock_sender.send_document.side_effect = MessageDeliveryError("Network timeout")

    with (
        patch.object(
            report_tasks.report_service,
            "get_daily_report_data",
            new_callable=AsyncMock,
            return_value=dummy_summary,
        ),
        patch.object(
            report_tasks.pdf_service,
            "generate_daily_summary_pdf",
            return_value=b"%PDF-1.4 dummy pdf bytes",
        ),
        patch.object(
            report_tasks,
            "MESSAGE_SENDER",
            new=mock_sender,
        ),
    ):
        # Should catch MessageDeliveryError and log without crashing
        await report_tasks.process_report(shop_id, recipient, target_date)
