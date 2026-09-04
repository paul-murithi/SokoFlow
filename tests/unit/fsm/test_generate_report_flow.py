from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.fsm.flows.generate_report import ReportFlow
from app.fsm.models import SessionContext, SessionState, UserSession
from app.workers.queues import QueueName


@pytest.mark.asyncio
async def test_handle_daily_report_with_cached_shop_id():
    shop_id = uuid4()
    recipient = "+254700000123"
    session = UserSession(
        phone=recipient,
        state=SessionState.IDLE,
        context=SessionContext(shop_id=shop_id),
    )
    flow = ReportFlow()

    with patch("app.fsm.flows.generate_report.report_task.apply_async") as mock_apply:
        await flow.handle_daily_report(session, "generate report")

        mock_apply.assert_called_once()
        _, kwargs = mock_apply.call_args
        assert kwargs["queue"] == QueueName.REPORTS
        assert kwargs["args"][0]["shop_id"] == str(shop_id)
        assert kwargs["args"][0]["recipient"] == recipient


@pytest.mark.asyncio
async def test_handle_daily_report_fetches_shop_id_when_missing():
    shop_id = uuid4()
    recipient = "+254700000456"
    session = UserSession(
        phone=recipient,
        state=SessionState.IDLE,
        context=SessionContext(shop_id=None),
    )
    flow = ReportFlow()

    with (
        patch.object(
            flow, "get_shop_id", new_callable=AsyncMock, return_value=shop_id
        ) as mock_get_shop,
        patch("app.fsm.flows.generate_report.report_task.apply_async") as mock_apply,
    ):
        await flow.handle_daily_report(session, "generate report")

        mock_get_shop.assert_called_once()
        assert session.context.shop_id == shop_id
        mock_apply.assert_called_once()
        _, kwargs = mock_apply.call_args
        assert kwargs["args"][0]["shop_id"] == str(shop_id)
