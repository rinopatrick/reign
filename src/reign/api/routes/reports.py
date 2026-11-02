"""Report generation routes."""

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
)

router = APIRouter()


@router.get("/monthly")
async def monthly_report(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    currency: str = "IDR",
    session: AsyncSession = Depends(profile_session),
):
    profile = validate_slug(request.headers.get("x-reign-profile", "") or "default")
    now = datetime.now()
    year = year or now.year
    month = month or now.month

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
        )
    )

    filename = f"report_{profile}_{year}{month:02d}_{currency}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/holdings")
async def holdings_report(request: Request, session: AsyncSession = Depends(profile_session)):
    """Holdings portfolio PDF for the active profile."""
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
    pdf_bytes = generate_holdings_report(items, profile=profile)
    filename = f"holdings_{profile}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
