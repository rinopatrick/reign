"""Category API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.adapters.repository import CategoryRepository
from reign.api.schemas import CategoryCreate, CategoryOut
from reign.domain.models import Category

router = APIRouter()


@router.get("", response_model=list[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_session)):
    repo = CategoryRepository(session)
    return await repo.list()


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    data: CategoryCreate, session: AsyncSession = Depends(get_session)
):
    repo = CategoryRepository(session)
    category = Category(**data.model_dump())
    return await repo.create(category)
