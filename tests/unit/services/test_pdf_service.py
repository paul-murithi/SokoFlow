import time
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.dto.sales import LowStockProductDTO
from app.schemas.sales import (
    DailySummaryResponse,
    TopProductRevenueInfo,
    TopProductUnitsInfo,
)
from app.services.pdf_service import PDFReportService


def test_generate_daily_summary_pdf_full_data():
    service = PDFReportService()
    summary = DailySummaryResponse(
        total_revenue=Decimal("12500.75"),
        transaction_count=15,
        top_products_by_units=[
            TopProductUnitsInfo(product_id=uuid4(), name="Sugar 1kg", units_sold=45),
            TopProductUnitsInfo(product_id=uuid4(), name="Cooking Oil 1L", units_sold=30),
        ],
        top_products_by_revenue=[
            TopProductRevenueInfo(
                product_id=uuid4(), name="Cooking Oil 1L", revenue=Decimal("7500.00")
            ),
            TopProductRevenueInfo(product_id=uuid4(), name="Sugar 1kg", revenue=Decimal("5000.75")),
        ],
        products_with_low_stock=[
            LowStockProductDTO(
                id=uuid4(), name="Maize Flour 2kg", quantity=3, low_stock_threshold=10
            )
        ],
    )

    start_time = time.perf_counter()
    pdf_bytes = service.generate_daily_summary_pdf(
        summary=summary, shop_name="Mama Mboga Shop", report_date=date(2026, 9, 3)
    )
    elapsed_time = time.perf_counter() - start_time

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")
    assert elapsed_time < 5.0  # Must complete within 5 seconds


def test_generate_daily_summary_pdf_empty_data():
    service = PDFReportService()
    summary = DailySummaryResponse(
        total_revenue=Decimal("0.00"),
        transaction_count=0,
        top_products_by_units=[],
        top_products_by_revenue=[],
        products_with_low_stock=[],
    )

    pdf_bytes = service.generate_daily_summary_pdf(summary=summary)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")
