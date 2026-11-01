"""Single settings service — replaces duplicated route/backup helpers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reign.domain.models import AppSetting


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    """Read a key, creating the default row when missing."""
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = AppSetting(key=key, value=default)
        session.add(row)
        await session.commit()
    return row.value or ""


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    """Upsert a key."""
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    await session.commit()
