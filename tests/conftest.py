"""Global pytest fixtures."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from reign.adapters.database import Base


@pytest.fixture
def sample_transactions() -> list[dict]:
    """Return sample transaction dicts for testing."""
    return [
        {
            "date": "2026-04-01",
            "description": "STARBUCKS INDONESIA",
            "amount": -75000.0,
            "currency": "IDR",
            "account_id": 1,
        },
        {
            "date": "2026-04-02",
            "description": "SALARY ACME CORP",
            "amount": 15000000.0,
            "currency": "IDR",
            "account_id": 1,
        },
    ]


async def init_test_db(db_path: str):
    """Create isolated test engine + session factory with tables + seed."""
    from reign.utils.seed import seed_categories, seed_demo_account

    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSession() as s:
        await seed_categories(s)
        await seed_demo_account(s)
    return test_engine, TestSession


@pytest.fixture(autouse=True)
async def _clean_db():
    """Ensure tables exist, wipe data, reseed — keeps legacy tests green."""
    from sqlalchemy import text

    from reign.adapters.database import AsyncSessionLocal, init_db
    from reign.utils.seed import seed_categories, seed_demo_account

    await init_db()
    async with AsyncSessionLocal() as s:
        for tbl in (
            "transaction_splits",
            "transactions",
            "budgets",
            "goals",
            "recurring_transactions",
            "accounts",
            "categories",
            "app_settings",
        ):
            await s.execute(text(f"DELETE FROM {tbl}"))
        await s.commit()
        await seed_categories(s)
        await seed_demo_account(s)
    yield
