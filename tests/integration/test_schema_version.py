"""Tests: schema version guard (ADR-001)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from reign.adapters.database import AsyncSessionLocal, Base
from reign.domain.models import Account, AppSetting, Transaction
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
async def test_schema_version_v7_upgrades_to_v8_without_data_loss(tmp_path):
    """v7 DB with one account + one transaction upgrades via ensure_schema_version."""
    db_path = tmp_path / "v7.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add(AppSetting(key="schema_version", value="7"))
        s.add(Account(name="Cash", type="cash", currency="IDR", initial_balance=Decimal("0")))
        await s.commit()
    async with factory() as s:
        acc = (await s.execute(select(Account))).scalars().first()
        s.add(
            Transaction(
                date=date(2026, 1, 1),
                description="EXP",
                amount=Decimal("-25000"),
                currency="IDR",
                account_id=acc.id,
            )
        )
        await s.commit()
    async with factory() as s:
        v = await ensure_schema_version(s)
        assert v == 8
    async with factory() as s:
        assert (await s.execute(select(Account))).scalars().all()
        assert (await s.execute(select(Transaction))).scalars().all()
        row = (
            await s.execute(select(AppSetting).where(AppSetting.key == "schema_version"))
        ).scalar_one()
        assert row.value == "8"
    await engine.dispose()


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
