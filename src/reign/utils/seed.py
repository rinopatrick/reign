"""Seed default categories and sample data."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reign.domain.models import Account, Category

DEFAULT_CATEGORIES = [
    # Income
    {"name": "Salary", "type": "income", "color": "#06D6A0", "keywords": "salary,gaji,thr,bonus"},
    {"name": "Investment", "type": "income", "color": "#118AB2", "keywords": "dividend,interest,deposito,bunga"},
    {"name": "Freelance", "type": "income", "color": "#073B4C", "keywords": "freelance,project,consulting"},
    # Expense
    {"name": "Food", "type": "expense", "color": "#EF476F", "keywords": "restaurant,starbucks,cafe,food,makan,kfc,mcd,gofood,grabfood,shopeefood"},
    {"name": "Transport", "type": "expense", "color": "#FFD166", "keywords": "gojek,grab,taxi,uber,bus,train,mrt,pertamina,shell,bp,transport"},
    {"name": "Utilities", "type": "expense", "color": "#06D6A0", "keywords": "pln,pdam,internet,wifi,phone,pulsa,listrik,air,gas"},
    {"name": "Healthcare", "type": "expense", "color": "#118AB2", "keywords": "pharmacy,doctor,hospital,clinic,apotek,dokter,rs"},
    {"name": "Entertainment", "type": "expense", "color": "#073B4C", "keywords": "netflix,spotify,youtube,cinema,bioskop,game,steam"},
    {"name": "Shopping", "type": "expense", "color": "#EF476F", "keywords": "tokopedia,shopee,lazada,amazon,mall,store,belanja"},
    {"name": "Transfer", "type": "transfer", "color": "#718096", "keywords": "transfer,tf,trf,kliring,rtgs"},
]


async def seed_categories(session: AsyncSession) -> None:
    """Insert default categories if none exist."""
    result = await session.execute(select(Category))
    if result.scalars().first():
        return
    for data in DEFAULT_CATEGORIES:
        session.add(Category(**data))
    await session.commit()


async def seed_demo_account(session: AsyncSession) -> None:
    """Insert a demo cash account if none exist."""
    result = await session.execute(select(Account))
    if result.scalars().first():
        return
    session.add(Account(name="Cash", type="cash", currency="IDR", initial_balance=Decimal("0")))
    await session.commit()
