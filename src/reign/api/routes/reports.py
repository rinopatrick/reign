"""Report generation routes."""

from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import validate_slug
from reign.adapters.repository import TransactionRepository
from reign.api.routes.profiles import profile_session
from reign.services.pdf_generator import MonthlyReportInput, generate_monthly_report

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
