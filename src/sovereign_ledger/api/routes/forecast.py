"""Forecast API routes."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sovereign_ledger.adapters.database import get_session
from sovereign_ledger.adapters.repository import RecurringRepository, TransactionRepository
from sovereign_ledger.api.schemas import ForecastResponse

router = APIRouter()


@router.get("", response_model=ForecastResponse)
async def get_forecast(
    currency: str = "IDR",
    session: AsyncSession = Depends(get_session),
):
    tx_repo = TransactionRepository(session)
    rec_repo = RecurringRepository(session)
    now = datetime.now()
    months = []
    for i in range(3):
        d = now.replace(day=1) + timedelta(days=i * 30)
        summary = await tx_repo.get_summary(d.year, d.month, currency)
        months.append({
            "label": d.strftime("%b %Y"),
            "income": summary["income"],
            "expense": summary["expense"],
            "net": summary["net"],
        })
    recurring = await rec_repo.list_active()
    from sovereign_ledger.api.schemas import RecurringOut
    return ForecastResponse(
        months=months,
        recurring=[RecurringOut.model_validate(r) for r in recurring],
    )
