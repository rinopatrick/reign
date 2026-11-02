"""Tests: schema version guard (ADR-001)."""

import pytest
from sqlalchemy import select

from reign.adapters.database import AsyncSessionLocal
from reign.domain.models import AppSetting
from reign.utils.seed import SCHEMA_VERSION, ensure_schema_version


@pytest.mark.asyncio
async def test_schema_version_stamped():
    async with AsyncSessionLocal() as s:
        v = await ensure_schema_version(s)
        assert v == SCHEMA_VERSION
        row = (
            await s.execute(select(AppSetting).where(AppSetting.key == "schema_version"))
        ).scalar_one()
        assert row.value == str(SCHEMA_VERSION)


@pytest.mark.asyncio
async def test_schema_version_newer_db_rejected():
    async with AsyncSessionLocal() as s:
        await ensure_schema_version(s)
        row = (
            await s.execute(select(AppSetting).where(AppSetting.key == "schema_version"))
        ).scalar_one()
        row.value = str(SCHEMA_VERSION + 99)
        s.add(row)
        await s.commit()
        with pytest.raises(RuntimeError, match="newer than app schema"):
            await ensure_schema_version(s)
        row.value = str(SCHEMA_VERSION)
        s.add(row)
        await s.commit()
