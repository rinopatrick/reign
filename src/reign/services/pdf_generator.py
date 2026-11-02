"""PDF report generator using ReportLab."""

import dataclasses
import datetime as dt
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


@dataclasses.dataclass
class MonthlyReportInput:
    """Bundled PDF inputs (keeps the generator signature small)."""

    year: int
    month: int
    currency: str = "IDR"
    summary: dict | None = None
    category_totals: list | None = None
    profile: str = "default"
    lang: str = "id"

    def resolved(self) -> tuple:
        summary = {
            "income": Decimal("0"),
            "expense": Decimal("0"),
            "net": Decimal("0"),
            **(self.summary or {}),
        }
        return (
            self.year,
            self.month,
            self.currency,
            summary,
            self.category_totals or [],
            self.profile,
        )


STRINGS = {
    "id": {
        "holdings_title": "Portofolio Holdings",
        "profile": "Profil",
        "generated": "Dibuat",
        "summary": "Ringkasan",
        "total_value": "Total nilai",
        "holding_unit": "holding",
        "holdings": "Holdings",
        "symbol": "Simbol",
        "units": "Unit",
        "avg_cost": "Rata-rata biaya",
        "price": "Harga",
        "value": "Nilai",
        "allocation": "Alokasi (berdasar nilai)",
        "no_holdings": "Belum ada holdings.",
        "footer": "Reign — Keuangan lokal-pertama",
        "from": "Dari",
        "to": "Ke",
        "monthly_title": "Laporan Bulanan",
        "income": "Pemasukan",
        "expense": "Pengeluaran",
        "net": "Bersih",
    },
    "en": {
        "holdings_title": "Holdings Portfolio",
        "profile": "Profile",
        "generated": "Generated",
        "summary": "Summary",
        "total_value": "Total value",
        "holding_unit": "holding(s)",
        "holdings": "Holdings",
        "symbol": "Symbol",
        "units": "Units",
        "avg_cost": "Avg Cost",
        "price": "Price",
        "value": "Value",
        "allocation": "Allocation (by value)",
        "no_holdings": "No holdings yet.",
        "footer": "Reign — Local-first personal finance",
        "from": "From",
        "to": "To",
        "monthly_title": "Monthly Report",
        "income": "Income",
        "expense": "Expense",
        "net": "Net",
    },
}


def _lang(lang: str) -> dict:
    return STRINGS.get(lang, STRINGS["id"])


def generate_monthly_report(report: MonthlyReportInput) -> bytes:
    """Generate a monthly finance report PDF."""
    year, month, currency, summary, category_totals, profile = report.resolved()
    t = _lang(report.lang)
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
            "Title",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=colors.HexColor("#0D1B2A"),
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#718096"),
            spaceAfter=18,
        ),
        "heading": ParagraphStyle(
            "Heading",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.HexColor("#1B4965"),
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#1A1A2E"),
            leading=14,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#718096")
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=colors.HexColor("#0D1B2A"),
        ),
    }

    # Header
    story.append(Paragraph(f"{t['monthly_title']} — {year}-{month:02d}", styles["title"]))
    story.append(
        Paragraph(
            f"{t['profile']}: {profile} · {t['generated']}: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["subtitle"],
        )
    )

    # Summary metrics table
    story.append(Paragraph(t["summary"], styles["heading"]))
    metric_data = [
        [
            Paragraph(t["income"], styles["metric_label"]),
            Paragraph(t["expense"], styles["metric_label"]),
            Paragraph(t["net"], styles["metric_label"]),
        ],
        [
            Paragraph(_fmt_money(summary["income"], currency), styles["metric_value"]),
            Paragraph(_fmt_money(abs(summary["expense"]), currency), styles["metric_value"]),
            Paragraph(_fmt_money(summary["net"], currency), styles["metric_value"]),
        ],
    ]
    metric_table = Table(metric_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#0077B6")),
            ]
        )
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
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
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
        story.append(cat_table)
    else:
        story.append(Paragraph("No expense data for this period.", styles["body"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Reign — Local-first personal finance", styles["subtitle"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


@dataclasses.dataclass
class HoldingRow:
    symbol: str
    units: str = "0"
    cost_basis: object = "0"
    current_price: object = "0"
    value: object = "0"
    pnl: object = "0"
    currency: str = "IDR"


def generate_sankey_report(data: dict, lang: str = "id") -> bytes:
    """Generate a cash-flow Sankey PDF: summary totals + flow table."""
    t = _lang(lang)
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
    title = ParagraphStyle(
        "STitle", fontName="Helvetica-Bold", fontSize=22, textColor=colors.HexColor("#0D1B2A")
    )
    body = ParagraphStyle(
        "SBody", fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#1A1A2E"), leading=14
    )
    story.append(
        Paragraph(
            f"{t['monthly_title']} — {data.get('year')}-{int(data.get('month', 1)):02d}", title
        )
    )
    story.append(
        Paragraph(
            f"{t['income']}: {data.get('total_in')} · {t['expense']}: {data.get('total_out')}",
            body,
        )
    )
    story.append(Spacer(1, 12))
    rows = [[t["from"], t["to"], t["value"]]] + [
        [str(link.get("source", "")), str(link.get("target", "")), str(link.get("value", ""))]
        for link in data.get("links", [])
    ]
    tbl = Table(rows, colWidths=[6 * cm, 6 * cm, 5 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 12))
    story.append(Paragraph(t["footer"], body))
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generate_holdings_report(
    holdings: list,
    profile: str = "default",
    currency: str = "IDR",
    lang: str = "id",
) -> bytes:
    """Generate a holdings portfolio PDF (summary + allocation + table)."""
    t = _lang(lang)
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
    title = ParagraphStyle(
        "HTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=colors.HexColor("#0D1B2A"),
        spaceAfter=6,
    )
    subtitle = ParagraphStyle(
        "HSub",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#718096"),
        spaceAfter=18,
    )
    heading = ParagraphStyle(
        "HHead",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#1B4965"),
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "HBody", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#1A1A2E"), leading=14
    )
    story.append(Paragraph(t["holdings_title"], title))
    story.append(
        Paragraph(
            f"{t['profile']}: {profile} · {t['generated']}: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            subtitle,
        )
    )
    total = sum((Decimal(str(h.get("value", 0))) for h in holdings), Decimal("0"))
    story.append(Paragraph(t["summary"], heading))
    story.append(
        Paragraph(
            f"{t['total_value']}: {currency} {total:,.2f} across {len(holdings)} {t['holding_unit']}.",
            body,
        )
    )
    story.append(Spacer(1, 12))
    story.append(Paragraph(t["holdings"], heading))
    if holdings:

        def _row(h):
            return [
                str(h.get("symbol", "")),
                str(h.get("units", "")),
                _fmt_money(Decimal(str(h.get("cost_basis", 0) or 0)), currency),
                _fmt_money(Decimal(str(h.get("current_price", 0) or 0)), currency),
                _fmt_money(Decimal(str(h.get("value", 0) or 0)), currency),
            ]

        rows = [[t["symbol"], t["units"], t["avg_cost"], t["price"], t["value"]]] + [
            _row(h) for h in holdings
        ]
        tbl = Table(rows, colWidths=[5 * cm, 3 * cm, 3 * cm, 3 * cm, 4 * cm])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B2A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ]
            )
        )
        story.append(tbl)
        story.append(Spacer(1, 12))
        story.append(Paragraph(t["allocation"], heading))
        for h in holdings:
            v = Decimal(str(h.get("value", 0) or 0))
            pct = (v / total * 100) if total else Decimal("0")
            story.append(Paragraph(f"{h.get('symbol', '')}: {pct:.1f}%", body))
    else:
        story.append(Paragraph(t["no_holdings"], body))
    story.append(Spacer(1, 12))
    story.append(Paragraph(t["footer"], subtitle))
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
