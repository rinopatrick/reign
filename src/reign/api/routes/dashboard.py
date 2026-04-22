"""Dashboard aggregation routes."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.adapters.repository import AccountRepository, TransactionRepository
from reign.api.schemas import CategoryTotal, DashboardSummary, TrendPoint

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    currency: str = "IDR", session: AsyncSession = Depends(get_session)
):
    now = datetime.now()
    account_repo = AccountRepository(session)
    tx_repo = TransactionRepository(session)

    accounts = await account_repo.list()
    total_balance = sum(a.initial_balance for a in accounts if a.currency == currency)

    summary = await tx_repo.get_summary(now.year, now.month, currency)

    return DashboardSummary(
        total_accounts=len(accounts),
        total_balance=total_balance,
        month_income=summary["income"],
        month_expense=summary["expense"],
        month_net=summary["net"],
        currency=currency,
    )


@router.get("/categories", response_model=list[CategoryTotal])
async def category_totals(
    year: int | None = None,
    month: int | None = None,
    currency: str = "IDR",
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    tx_repo = TransactionRepository(session)
    rows = await tx_repo.get_category_totals(year, month, currency)
    return [CategoryTotal(name=name, total=total) for name, total in rows]


@router.get("/trends", response_model=list[TrendPoint])
async def monthly_trends(
    months: int = 6,
    currency: str = "IDR",
    session: AsyncSession = Depends(get_session),
):
    tx_repo = TransactionRepository(session)
    rows = await tx_repo.get_monthly_trends(months, currency)
    return [TrendPoint(**r) for r in rows]
