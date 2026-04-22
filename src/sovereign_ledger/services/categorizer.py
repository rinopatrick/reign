"""Auto-categorization engine using keyword rules."""


from sqlalchemy.ext.asyncio import AsyncSession

from sovereign_ledger.adapters.repository import CategoryRepository
from sovereign_ledger.domain.models import Category, Transaction


def match_category(description: str, categories: list[Category]) -> int | None:
    """Return best-matching category_id based on keywords."""
    desc_lower = description.lower()
    best_score = 0
    best_id = None
    for cat in categories:
        if not cat.keywords:
            continue
        keywords = [k.strip().lower() for k in cat.keywords.split(",") if k.strip()]
        score = sum(1 for kw in keywords if kw in desc_lower)
        if score > best_score:
            best_score = score
            best_id = cat.id
    return best_id


async def categorize_transactions(
    session: AsyncSession, transactions: list[Transaction]
) -> None:
    """Auto-assign categories to uncategorized transactions."""
    repo = CategoryRepository(session)
    categories = list(await repo.list())
    for tx in transactions:
        if tx.category_id is not None:
            continue
        cat_id = match_category(tx.description, categories)
        if cat_id:
            tx.category_id = cat_id
