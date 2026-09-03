from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.sales import DailySummaryResponse


class PDFReportService:
    def generate_daily_summary_pdf(
        self,
        summary: DailySummaryResponse,
        shop_name: str = "SokoFlow Shop",
        report_date: date | None = None,
    ) -> bytes:
        """
        Generate a PDF document binary stream from a DailySummaryResponse object.
        Execution is optimized to complete within 5 seconds.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#4A5568"),
            spaceAfter=15,
        )
        section_heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=12,
            spaceAfter=6,
        )
        cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#2D3748"),
        )
        cell_header_style = ParagraphStyle(
            "TableHeaderCell",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )
        empty_text_style = ParagraphStyle(
            "EmptyText",
            parent=styles["Italic"],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#718096"),
            spaceAfter=8,
        )

        story = []

        # Header & Metadata
        date_str = (report_date or date.today()).strftime("%B %d, %Y")
        story.append(Paragraph("SokoFlow Daily Report", title_style))
        story.append(
            Paragraph(
                f"<b>Shop:</b> {shop_name} &nbsp;|&nbsp; <b>Date:</b> {date_str}", subtitle_style
            )
        )
        story.append(Spacer(1, 5))

        # Key Metrics Summary Box
        metrics_data = [
            [
                Paragraph("<b>Total Revenue</b>", cell_header_style),
                Paragraph("<b>Total Transactions</b>", cell_header_style),
            ],
            [
                Paragraph(f"<b>KES {summary.total_revenue:,.2f}</b>", cell_style),
                Paragraph(f"<b>{summary.transaction_count}</b>", cell_style),
            ],
        ]
        metrics_table = Table(metrics_data, colWidths=[270, 270])
        metrics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EBF8FF")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ]
            )
        )
        story.append(metrics_table)
        story.append(Spacer(1, 12))

        # Top Products by Units Sold
        story.append(Paragraph("Top Products by Units Sold", section_heading_style))
        if summary.top_products_by_units:
            units_table_data = [
                [
                    Paragraph("Product Name", cell_header_style),
                    Paragraph("Units Sold", cell_header_style),
                ]
            ]
            for unit_item in summary.top_products_by_units:
                units_table_data.append(
                    [
                        Paragraph(unit_item.name, cell_style),
                        Paragraph(str(unit_item.units_sold), cell_style),
                    ]
                )
            units_table = Table(units_table_data, colWidths=[380, 160])
            units_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#F7FAFC")],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ]
                )
            )
            story.append(units_table)
        else:
            story.append(Paragraph("No units sold recorded for this period.", empty_text_style))

        story.append(Spacer(1, 10))

        # Top Products by Revenue
        story.append(Paragraph("Top Products by Revenue", section_heading_style))
        if summary.top_products_by_revenue:
            rev_table_data = [
                [
                    Paragraph("Product Name", cell_header_style),
                    Paragraph("Revenue", cell_header_style),
                ]
            ]
            for rev_item in summary.top_products_by_revenue:
                rev_table_data.append(
                    [
                        Paragraph(rev_item.name, cell_style),
                        Paragraph(f"KES {rev_item.revenue:,.2f}", cell_style),
                    ]
                )
            rev_table = Table(rev_table_data, colWidths=[380, 160])
            rev_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#F7FAFC")],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ]
                )
            )
            story.append(rev_table)
        else:
            story.append(Paragraph("No revenue recorded for this period.", empty_text_style))

        story.append(Spacer(1, 10))

        # Low Stock Alerts
        story.append(Paragraph("Low Stock Alerts", section_heading_style))
        if summary.products_with_low_stock:
            low_stock_table_data = [
                [
                    Paragraph("Product Name", cell_header_style),
                    Paragraph("Current Stock", cell_header_style),
                    Paragraph("Threshold", cell_header_style),
                ]
            ]
            for low_stock_item in summary.products_with_low_stock:
                low_stock_table_data.append(
                    [
                        Paragraph(low_stock_item.name, cell_style),
                        Paragraph(str(low_stock_item.quantity), cell_style),
                        Paragraph(str(low_stock_item.low_stock_threshold), cell_style),
                    ]
                )
            low_stock_table = Table(low_stock_table_data, colWidths=[280, 130, 130])
            low_stock_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C53030")),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#FFF5F5")],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FEB2B2")),
                    ]
                )
            )
            story.append(low_stock_table)
        else:
            story.append(Paragraph("No products currently low on stock.", empty_text_style))

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
