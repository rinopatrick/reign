"""Budget API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.adapters.repository import BudgetRepository, CategoryRepository, TransactionRepository
from reign.api.schemas import BudgetCreate, BudgetOut
from reign.domain.models import Budget
from reign.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=list[BudgetOut])
async def list_budgets(year: int, month: int, session: AsyncSession = Depends(get_session)):
    repo = BudgetRepository(session)
    budgets = await repo.list(year, month)
    # Compute spent per budget
    tx_repo = TransactionRepository(session)
    for b in budgets:
        summary = await tx_repo.get_category_totals(year, month, b.currency)
        spent = sum(abs(total) for name, total in summary if b.category and name == b.category.name)
        b.spent = spent
    return budgets


@router.post("", response_model=BudgetOut, status_code=201)
async def create_budget(data: BudgetCreate, session: AsyncSession = Depends(get_session)):
    try:
        await CategoryRepository(session).get(data.category_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    repo = BudgetRepository(session)
    budget = Budget(**data.model_dump())
    return await repo.create_or_update(budget)
