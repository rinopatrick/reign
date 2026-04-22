"""Goal API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sovereign_ledger.adapters.database import get_session
from sovereign_ledger.adapters.repository import GoalRepository
from sovereign_ledger.api.schemas import GoalCreate, GoalOut
from sovereign_ledger.domain.models import Goal
from sovereign_ledger.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=list[GoalOut])
async def list_goals(session: AsyncSession = Depends(get_session)):
    repo = GoalRepository(session)
    return await repo.list()


@router.post("", response_model=GoalOut, status_code=201)
async def create_goal(
    data: GoalCreate, session: AsyncSession = Depends(get_session)
):
    repo = GoalRepository(session)
    goal = Goal(**data.model_dump())
    return await repo.create(goal)


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: int, session: AsyncSession = Depends(get_session)
):
    repo = GoalRepository(session)
    try:
        await repo.delete(goal_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "Goal deleted"}
