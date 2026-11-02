"""Budget API routes - single-query spent via TransactionRepository.get_spent_map."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.repository import BudgetRepository, CategoryRepository, TransactionRepository
from reign.api.routes.profiles import profile_session
from reign.api.schemas import BudgetCreate, BudgetOut
from reign.domain.models import Budget
from reign.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=list[BudgetOut])
async def list_budgets(year: int, month: int, session: AsyncSession = Depends(profile_session)):
    repo = BudgetRepository(session)
    budgets = await repo.list(year, month)
    # Single aggregated query for all (category, currency) spent.
    tx_repo = TransactionRepository(session)
    spent_map = await tx_repo.get_spent_map(year, month)
    for b in budgets:
        key = (b.category_id, b.currency) if b.category_id else None
        b.spent = spent_map.get(key, Decimal("0")) if key else Decimal("0")
    return budgets


@router.post("", response_model=BudgetOut, status_code=201)
async def create_budget(data: BudgetCreate, session: AsyncSession = Depends(profile_session)):
    try:
        await CategoryRepository(session).get(data.category_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    repo = BudgetRepository(session)
    budget = Budget(**data.model_dump())
    return await repo.create_or_update(budget)
