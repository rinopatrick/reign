"""Application settings API routes (thin — logic lives in services.settings)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reign.api.routes.profiles import profile_session
from reign.domain.models import AppSetting
from reign.services.notify import generate_vapid_keys
from reign.services.settings import get_setting, set_setting

router = APIRouter()

MAX_SETTING_VALUE_LEN = 256

ALLOWED_SETTING_KEYS = {
    "auto_backup_enabled",
    "auto_backup_interval_days",
    "auto_backup_last_run",
    "auto_backup_compress",
    "theme",
    "default_currency",
}


class SettingUpdate(BaseModel):
    value: str


@router.post("/vapid/generate")
async def generate_vapid():
    """Generate a VAPID ES256 keypair. Private key is shown ONCE — save it to env."""
    public_key, private_key = generate_vapid_keys()
    return {
        "public_key": public_key,
        "private_key": private_key,
        "env_hint": "Set VAPID_PUBLIC_KEY + VAPID_PRIVATE_KEY, then restart.",
    }


@router.get("")
async def list_settings(session: AsyncSession = Depends(profile_session)):
    result = await session.execute(select(AppSetting))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


@router.get("/{key}")
async def get_setting_route(key: str, session: AsyncSession = Depends(profile_session)):
    value = await get_setting(session, key)
    return {"key": key, "value": value}


@router.put("/{key}")
async def update_setting(
    key: str, payload: SettingUpdate, session: AsyncSession = Depends(profile_session)
):
    if key not in ALLOWED_SETTING_KEYS:
        raise HTTPException(status_code=400, detail="Unknown setting key")
    if len(payload.value) > MAX_SETTING_VALUE_LEN:
        raise HTTPException(status_code=400, detail="Setting value too long (max 256)")
    await set_setting(session, key, payload.value)
    return {"key": key, "value": payload.value}
