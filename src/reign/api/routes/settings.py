"""Application settings API routes (thin — logic lives in services.settings)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.domain.models import AppSetting
from reign.services.settings import get_setting, set_setting

router = APIRouter()

MAX_SETTING_VALUE_LEN = 256

ALLOWED_SETTING_KEYS = {
    "auto_backup_enabled",
    "auto_backup_interval_days",
    "auto_backup_last_run",
    "theme",
    "default_currency",
}


class SettingUpdate(BaseModel):
    value: str


@router.get("")
async def list_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AppSetting))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


@router.get("/{key}")
async def get_setting_route(key: str, session: AsyncSession = Depends(get_session)):
    value = await get_setting(session, key)
    return {"key": key, "value": value}


@router.put("/{key}")
async def update_setting(
    key: str, payload: SettingUpdate, session: AsyncSession = Depends(get_session)
):
    if key not in ALLOWED_SETTING_KEYS:
        raise HTTPException(status_code=400, detail="Unknown setting key")
    if len(payload.value) > MAX_SETTING_VALUE_LEN:
        raise HTTPException(status_code=400, detail="Setting value too long (max 256)")
    await set_setting(session, key, payload.value)
    return {"key": key, "value": payload.value}
