"""Recurring transaction API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sovereign_ledger.adapters.database import get_session
from sovereign_ledger.adapters.repository import RecurringRepository
from sovereign_ledger.api.schemas import RecurringCreate, RecurringOut
from sovereign_ledger.domain.models import RecurringTransaction
from sovereign_ledger.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=list[RecurringOut])
async def list_recurring(session: AsyncSession = Depends(get_session)):
    repo = RecurringRepository(session)
    recs = await repo.list()
    return [RecurringOut.model_validate(r) for r in recs]


@router.post("", response_model=RecurringOut, status_code=201)
async def create_recurring(
    data: RecurringCreate, session: AsyncSession = Depends(get_session)
):
    repo = RecurringRepository(session)
    rec = RecurringTransaction(**data.model_dump())
    rec = await repo.create(rec)
    return RecurringOut.model_validate(rec)


@router.delete("/{rec_id}")
async def delete_recurring(
    rec_id: int, session: AsyncSession = Depends(get_session)
):
    repo = RecurringRepository(session)
    try:
        await repo.delete(rec_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "Recurring transaction deleted"}
