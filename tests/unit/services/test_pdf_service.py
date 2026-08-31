from decimal import Decimal

from app.schemas.sales import DailySummaryResponse
from app.services.pdf_service import PDFReportService


def test_generate_daily_summary_pdf_stub():
    service = PDFReportService()
    summary = DailySummaryResponse(total_revenue=Decimal("100.00"), transaction_count=1)
    pdf_bytes = service.generate_daily_summary_pdf(summary)
    assert isinstance(pdf_bytes, bytes)
