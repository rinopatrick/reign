"""PDF report generator using ReportLab."""

from datetime import datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _fmt_money(value: Decimal, currency: str = "IDR") -> str:
    if currency == "IDR":
        return f"Rp {value:,.0f}".replace(",", ".")
    return f"{currency} {value:,.2f}"


def generate_monthly_report(
    year: int,
    month: int,
    currency: str,
    summary: dict[str, Decimal],
    category_totals: list[tuple[str, Decimal]],
) -> bytes:
    """Generate a monthly finance report PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story: list = []
    styles = {
        "title": ParagraphStyle(
            "Title", fontName="Helvetica-Bold", fontSize=22, textColor=colors.HexColor("#0D1B2A"), spaceAfter=6
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#718096"), spaceAfter=18
        ),
        "heading": ParagraphStyle(
            "Heading", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1B4965"), spaceAfter=6
        ),
        "body": ParagraphStyle(
            "Body", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#1A1A2E"), leading=14
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#718096")
        ),
        "metric_value": ParagraphStyle(
            "MetricValue", fontName="Helvetica-Bold", fontSize=14, textColor=colors.HexColor("#0D1B2A")
        ),
    }

    # Header
    story.append(Paragraph(f"Monthly Report — {year}-{month:02d}", styles["title"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["subtitle"]))

    # Summary metrics table
    story.append(Paragraph("Summary", styles["heading"]))
    metric_data = [
        [
            Paragraph("Income", styles["metric_label"]),
            Paragraph("Expense", styles["metric_label"]),
            Paragraph("Net", styles["metric_label"]),
        ],
        [
            Paragraph(_fmt_money(summary["income"], currency), styles["metric_value"]),
            Paragraph(_fmt_money(abs(summary["expense"]), currency), styles["metric_value"]),
            Paragraph(_fmt_money(summary["net"], currency), styles["metric_value"]),
        ],
    ]
    metric_table = Table(metric_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
    metric_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#0077B6")),
        ])
    )
    story.append(metric_table)
    story.append(Spacer(1, 18))

    # Category breakdown
    story.append(Paragraph("Spending by Category", styles["heading"]))
    if category_totals:
        cat_data = [["Category", "Amount"]]
        for name, total in category_totals:
            cat_data.append([name, _fmt_money(total, currency)])
        cat_table = Table(cat_data, colWidths=[10 * cm, 5 * cm])
        cat_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ])
        )
        story.append(cat_table)
    else:
        story.append(Paragraph("No expense data for this period.", styles["body"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Sovereign Ledger — Local-first personal finance", styles["subtitle"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
