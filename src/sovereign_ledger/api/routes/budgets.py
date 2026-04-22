"""Budget API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sovereign_ledger.adapters.database import get_session
from sovereign_ledger.adapters.repository import BudgetRepository
from sovereign_ledger.api.schemas import BudgetCreate, BudgetOut
from sovereign_ledger.domain.models import Budget

router = APIRouter()


@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    year: int, month: int, session: AsyncSession = Depends(get_session)
):
    repo = BudgetRepository(session)
    budgets = await repo.list(year, month)
    # Compute spent per budget
    from sovereign_ledger.adapters.repository import TransactionRepository
    tx_repo = TransactionRepository(session)
    for b in budgets:
        summary = await tx_repo.get_category_totals(year, month, b.currency)
        spent = sum(abs(total) for name, total in summary if b.category and name == b.category.name)
        b.spent = spent
    return budgets


@router.post("", response_model=BudgetOut, status_code=201)
async def create_budget(
    data: BudgetCreate, session: AsyncSession = Depends(get_session)
):
    repo = BudgetRepository(session)
    budget = Budget(**data.model_dump())
    return await repo.create_or_update(budget)
