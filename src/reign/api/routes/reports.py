"""Report generation routes."""
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.adapters.repository import TransactionRepository
from reign.services.pdf_generator import generate_monthly_report

router = APIRouter()


@router.get("/monthly")
async def monthly_report(
    year: int | None = None,
    month: int | None = None,
    currency: str = "IDR",
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    tx_repo = TransactionRepository(session)
    summary = await tx_repo.get_summary(year, month, currency)
    category_rows = await tx_repo.get_category_totals(year, month, currency)

    pdf_bytes = generate_monthly_report(
        year=year,
        month=month,
        currency=currency,
        summary=summary,
        category_totals=category_rows,
    )

    filename = f"report_{year}{month:02d}_{currency}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
