"""Forecast API routes - projection from active recurring (future, calendar-correct)."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.adapters.repository import RecurringRepository
from reign.api.schemas import ForecastResponse, RecurringOut
from reign.domain.period import Period

router = APIRouter()


@router.get("", response_model=ForecastResponse)
async def get_forecast(currency: str = "IDR", session: AsyncSession = Depends(get_session)):
    rec_repo = RecurringRepository(session)
    now = datetime.now()
    current = Period.from_raw(now.year, now.month, currency)
    recurring = await rec_repo.list_active()
    active = [r for r in recurring if (r.currency or "IDR") == current.as_currency_str()]
    months = []
    for i in range(3):
        p = current.add_months(i)
        income = sum((r.amount for r in active if r.amount > 0), Decimal("0"))
        expense = sum((r.amount for r in active if r.amount < 0), Decimal("0"))
        months.append(
            {
                "label": p.label(),
                "income": income,
                "expense": expense,
                "net": income + expense,
            }
        )
    return ForecastResponse(
        months=months,
        recurring=[RecurringOut.model_validate(r) for r in recurring],
    )
