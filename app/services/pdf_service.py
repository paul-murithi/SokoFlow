from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate

from app.schemas.sales import DailySummaryResponse


class PDFReportService:
    def generate_daily_summary_pdf(
        self, summary: DailySummaryResponse, shop_name: str = "SokoFlow Shop"
    ) -> bytes:
        """
        Generate a PDF document stream from a DailySummaryResponse object.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        # TODO: Add story elements (title, summary stats table, top products table)
        doc.build([])
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
