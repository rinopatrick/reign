"""Report generation routes."""

import dataclasses
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import validate_slug
from reign.adapters.repository import HoldingRepository, TransactionRepository
from reign.api.routes.profiles import profile_session
from reign.services.pdf_generator import (
    MonthlyReportInput,
    generate_holdings_report,
    generate_monthly_report,
    generate_sankey_report,
)

router = APIRouter()


@dataclasses.dataclass
class MonthlyParams:
    """Bundled monthly-report query params (keeps the endpoint signature small)."""

    year: int | None = None
    month: int | None = None
    currency: str = "IDR"
    lang: str = "id"


@router.get("/monthly")
async def monthly_report(
    request: Request,
    params: MonthlyParams = Depends(),
    session: AsyncSession = Depends(profile_session),
):
    profile = validate_slug(request.headers.get("x-reign-profile", "") or "default")
    now = datetime.now()
    year = params.year or now.year
    month = params.month or now.month
    currency = params.currency
    lang = params.lang if params.lang in ("id", "en") else "id"

    tx_repo = TransactionRepository(session)
    summary = await tx_repo.get_summary(year, month, currency)
    category_rows = await tx_repo.get_category_totals(year, month, currency)

    pdf_bytes = generate_monthly_report(
        MonthlyReportInput(
            year=year,
            month=month,
            currency=currency,
            summary=summary,
            category_totals=category_rows,
            profile=profile,
            lang=lang,
        )
    )

    filename = f"report_{profile}_{year}{month:02d}_{currency}_{lang}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/sankey")
async def sankey(
    year: int | None = None,
    month: int | None = None,
    currency: str = "IDR",
    session: AsyncSession = Depends(profile_session),
):
    """Cash-flow Sankey nodes/links: income categories -> expense categories + remainder."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    tx_repo = TransactionRepository(session)
    income_cats = await tx_repo.get_income_by_category(year, month, currency)
    expense_cats = await tx_repo.get_category_totals(year, month, currency)
    cat_ids = await tx_repo.get_category_id_map()
    total_in = sum((Decimal(str(v)) for _, v in income_cats), Decimal("0"))
    total_out = sum((abs(Decimal(str(v))) for _, v in expense_cats), Decimal("0"))
    remainder = total_in - total_out
    nodes = [{"id": "income", "label": "Pemasukan"}]
    nodes += [{"id": f"in:{name}", "label": name} for name, _ in income_cats]
    nodes += [{"id": f"out:{name}", "label": name} for name, _ in expense_cats]
    if remainder > 0:
        nodes.append({"id": "saved", "label": "Sisa"})
    links = [
        {
            "source": "income",
            "target": f"in:{name}",
            "value": str(Decimal(str(v))),
            "category_id": cat_ids.get(name),
            "category": name,
        }
        for name, v in income_cats
    ]
    links += [
        {
            "source": "income",
            "target": f"out:{name}",
            "value": str(abs(Decimal(str(v)))),
            "category_id": cat_ids.get(name),
            "category": name,
        }
        for name, v in expense_cats
    ]
    if remainder > 0:
        links.append(
            {
                "source": "income",
                "target": "saved",
                "value": str(remainder),
                "breakdown": {
                    "income": [
                        {"category": name, "value": str(Decimal(str(v)))} for name, v in income_cats
                    ],
                    "expense": [
                        {"category": name, "value": str(abs(Decimal(str(v))))}
                        for name, v in expense_cats
                    ],
                },
            }
        )
    return {
        "year": year,
        "month": month,
        "currency": currency,
        "total_in": str(total_in),
        "total_out": str(total_out),
        "nodes": nodes,
        "links": links,
    }


@router.get("/sankey/pdf")
async def sankey_pdf(
    year: int | None = None,
    month: int | None = None,
    currency: str = "IDR",
    lang: str = "id",
    session: AsyncSession = Depends(profile_session),
):
    """Sankey cash-flow PDF for the active month."""
    data = await sankey(year=year, month=month, currency=currency, session=session)
    pdf_bytes = generate_sankey_report(data, lang=lang if lang in ("id", "en") else "id")
    filename = f"sankey_{data['year']}{int(data['month']):02d}_{lang}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/holdings")
async def holdings_report(
    request: Request, lang: str = "id", session: AsyncSession = Depends(profile_session)
):
    """Holdings portfolio PDF for the active profile."""
    lang = lang if lang in ("id", "en") else "id"
    profile = validate_slug(request.headers.get("x-reign-profile", "") or "default")
    repo = HoldingRepository(session)
    rows = await repo.list()
    items = [
        {
            "symbol": h.symbol,
            "units": str(h.units),
            "cost_basis": str(h.cost_basis),
            "current_price": str(h.current_price),
            "value": str((h.units or Decimal("0")) * (h.current_price or Decimal("0"))),
            "currency": h.currency,
        }
        for h in rows
    ]
    pdf_bytes = generate_holdings_report(items, profile=profile, lang=lang)
    filename = f"holdings_{profile}_{lang}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
