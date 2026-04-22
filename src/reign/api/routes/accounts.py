"""Account API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.adapters.repository import AccountRepository
from reign.api.schemas import AccountCreate, AccountOut
from reign.domain.models import Account
from reign.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=list[AccountOut])
async def list_accounts(session: AsyncSession = Depends(get_session)):
    repo = AccountRepository(session)
    return await repo.list()


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    data: AccountCreate, session: AsyncSession = Depends(get_session)
):
    repo = AccountRepository(session)
    account = Account(**data.model_dump())
    return await repo.create(account)


@router.delete("/{account_id}")
async def delete_account(account_id: int, session: AsyncSession = Depends(get_session)):
    repo = AccountRepository(session)
    try:
        await repo.delete(account_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "Account deleted"}
