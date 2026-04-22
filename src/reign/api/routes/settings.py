"""Application settings API routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import AsyncSessionLocal, get_session
from reign.domain.models import AppSetting

router = APIRouter()


class SettingUpdate(BaseModel):
    value: str


async def _get_or_create(session: AsyncSession, key: str, default: str = "") -> str:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = AppSetting(key=key, value=default)
        session.add(setting)
        await session.commit()
    return setting.value or ""


@router.get("")
async def list_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AppSetting))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


@router.get("/{key}")
async def get_setting(key: str, session: AsyncSession = Depends(get_session)):
    value = await _get_or_create(session, key)
    return {"key": key, "value": value}


@router.put("/{key}")
async def update_setting(key: str, payload: SettingUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = AppSetting(key=key, value=payload.value)
        session.add(setting)
    else:
        setting.value = payload.value
    await session.commit()
    return {"key": key, "value": payload.value}
