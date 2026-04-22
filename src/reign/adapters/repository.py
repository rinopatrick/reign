"""Repository layer for database operations."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reign.domain.models import (
    Account,
    Budget,
    Category,
    Goal,
    RecurringTransaction,
    Transaction,
)
from reign.exceptions import NotFoundError


class AccountRepository:
    """Repository for Account entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[Account]:
        result = await self._session.execute(select(Account))
        return result.scalars().all()

    async def get(self, account_id: int) -> Account:
        account = await self._session.get(Account, account_id)
        if not account:
            raise NotFoundError(f"Account {account_id} not found")
        return account

    async def create(self, account: Account) -> Account:
        self._session.add(account)
        await self._session.commit()
        await self._session.refresh(account)
        return account

    async def delete(self, account_id: int) -> None:
        account = await self.get(account_id)
        await self._session.delete(account)
        await self._session.commit()


class CategoryRepository:
    """Repository for Category entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[Category]:
        result = await self._session.execute(select(Category))
        return result.scalars().all()

    async def get(self, category_id: int) -> Category:
        category = await self._session.get(Category, category_id)
        if not category:
            raise NotFoundError(f"Category {category_id} not found")
        return category

    async def create(self, category: Category) -> Category:
        self._session.add(category)
        await self._session.commit()
        await self._session.refresh(category)
        return category

    async def get_by_name(self, name: str) -> Category | None:
        result = await self._session.execute(
            select(Category).where(Category.name == name)
        )
        return result.scalar_one_or_none()


class TransactionRepository:
    """Repository for Transaction entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(
        self,
        *,
        account_id: int | None = None,
        category_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        q: str | None = None,
        tag: str | None = None,
        include_deleted: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> Sequence[Transaction]:
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.category))
            .order_by(Transaction.date.desc())
        )
        if not include_deleted:
            stmt = stmt.where(Transaction.is_deleted == False)
        if account_id:
            stmt = stmt.where(Transaction.account_id == account_id)
        if category_id:
            stmt = stmt.where(Transaction.category_id == category_id)
        if start_date:
            stmt = stmt.where(Transaction.date >= start_date)
        if end_date:
            stmt = stmt.where(Transaction.date <= end_date)
        if q:
            stmt = stmt.where(
                or_(
                    Transaction.description.ilike(f"%{q}%"),
                    Transaction.notes.ilike(f"%{q}%"),
                    Transaction.tags.ilike(f"%{q}%"),
                )
            )
        if tag:
            stmt = stmt.where(Transaction.tags.ilike(f"%{tag}%"))
        result = await self._session.execute(stmt.limit(limit).offset(offset))
        return result.scalars().all()

    async def create(self, transaction: Transaction) -> Transaction:
        self._session.add(transaction)
        await self._session.commit()
        await self._session.refresh(transaction)
        # Re-fetch with category eager-loaded to avoid MissingGreenlet in response serialization
        result = await self._session.execute(
            select(Transaction).options(selectinload(Transaction.category)).where(Transaction.id == transaction.id)
        )
        return result.scalar_one()

    async def create_transfer(self, from_tx: Transaction, to_tx: Transaction) -> tuple[Transaction, Transaction]:
        self._session.add(from_tx)
        self._session.add(to_tx)
        await self._session.commit()
        await self._session.refresh(from_tx)
        await self._session.refresh(to_tx)
        return from_tx, to_tx

    async def create_many(self, transactions: Sequence[Transaction]) -> None:
        self._session.add_all(transactions)
        await self._session.commit()

    async def delete(self, transaction_id: int) -> None:
        tx = await self._session.get(Transaction, transaction_id)
        if not tx:
            raise NotFoundError(f"Transaction {transaction_id} not found")
        tx.is_deleted = True
        await self._session.commit()

    async def hard_delete(self, transaction_id: int) -> None:
        tx = await self._session.get(Transaction, transaction_id)
        if not tx:
            raise NotFoundError(f"Transaction {transaction_id} not found")
        await self._session.delete(tx)
        await self._session.commit()

    async def bulk_delete(self, ids: list[int]) -> None:
        for tx_id in ids:
            tx = await self._session.get(Transaction, tx_id)
            if tx:
                tx.is_deleted = True
        await self._session.commit()

    async def reconcile(self, transaction_id: int) -> None:
        tx = await self._session.get(Transaction, transaction_id)
        if not tx:
            raise NotFoundError(f"Transaction {transaction_id} not found")
        tx.is_reconciled = True
        await self._session.commit()

    async def bulk_reconcile(self, ids: list[int]) -> None:
        for tx_id in ids:
            tx = await self._session.get(Transaction, tx_id)
            if tx:
                tx.is_reconciled = True
        await self._session.commit()

    async def bulk_update(self, ids: list[int], category_id: int | None = None, date: date | None = None) -> None:
        for tx_id in ids:
            tx = await self._session.get(Transaction, tx_id)
            if tx:
                if category_id is not None:
                    tx.category_id = category_id
                if date is not None:
                    tx.date = date
        await self._session.commit()

    async def get_summary(
        self, year: int, month: int, currency: str = "IDR"
    ) -> dict[str, Decimal]:
        """Return income, expense, and net for a month."""
        base = (
            select(func.coalesce(func.sum(Transaction.amount), Decimal("0")))
            .where(extract("year", Transaction.date) == year)
            .where(extract("month", Transaction.date) == month)
            .where(Transaction.currency == currency)
            .where(Transaction.is_deleted == False)
            .where(Transaction.transaction_type != "transfer")
        )
        income = (await self._session.execute(base.where(Transaction.amount > 0))).scalar_one()
        expense = (await self._session.execute(base.where(Transaction.amount < 0))).scalar_one()
        return {
            "income": income,
            "expense": expense,
            "net": income + expense,
        }

    async def get_category_totals(
        self, year: int, month: int, currency: str = "IDR"
    ) -> Sequence[tuple[str, Decimal]]:
        """Return spending per category for a month."""
        stmt = (
            select(Category.name, func.sum(Transaction.amount))
            .join(Transaction.category)
            .where(extract("year", Transaction.date) == year)
            .where(extract("month", Transaction.date) == month)
            .where(Transaction.currency == currency)
            .where(Transaction.amount < 0)
            .where(Transaction.is_deleted == False)
            .where(Transaction.transaction_type != "transfer")
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount))
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def get_monthly_trends(
        self, months: int = 6, currency: str = "IDR"
    ) -> list[dict]:
        """Return income/expense per month for the last N months."""
        from datetime import datetime
        now = datetime.now()
        results = []
        for i in range(months - 1, -1, -1):
            d = now.replace(day=1) - timedelta(days=i * 30)
            summary = await self.get_summary(d.year, d.month, currency)
            results.append({
                "label": d.strftime("%b %Y"),
                "year": d.year,
                "month": d.month,
                "income": summary["income"],
                "expense": summary["expense"],
                "net": summary["net"],
            })
        return results


class BudgetRepository:
    """Repository for Budget entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, year: int, month: int) -> Sequence[Budget]:
        result = await self._session.execute(
            select(Budget)
            .options(selectinload(Budget.category))
            .where(Budget.year == year, Budget.month == month)
        )
        return result.scalars().all()

    async def create_or_update(self, budget: Budget) -> Budget:
        existing = await self._session.execute(
            select(Budget).where(
                Budget.year == budget.year,
                Budget.month == budget.month,
                Budget.category_id == budget.category_id,
            )
        )
        existing = existing.scalar_one_or_none()
        if existing:
            existing.amount = budget.amount
            existing.currency = budget.currency
            existing.rollover = budget.rollover
            await self._session.commit()
            await self._session.refresh(existing)
            budget_id = existing.id
        else:
            self._session.add(budget)
            await self._session.commit()
            await self._session.refresh(budget)
            budget_id = budget.id
        # Re-fetch with category eager-loaded
        result = await self._session.execute(
            select(Budget).options(selectinload(Budget.category)).where(Budget.id == budget_id)
        )
        return result.scalar_one()


class GoalRepository:
    """Repository for Goal entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[Goal]:
        result = await self._session.execute(select(Goal))
        return result.scalars().all()

    async def create(self, goal: Goal) -> Goal:
        self._session.add(goal)
        await self._session.commit()
        await self._session.refresh(goal)
        return goal

    async def delete(self, goal_id: int) -> None:
        goal = await self._session.get(Goal, goal_id)
        if not goal:
            raise NotFoundError(f"Goal {goal_id} not found")
        await self._session.delete(goal)
        await self._session.commit()


class RecurringRepository:
    """Repository for RecurringTransaction entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[RecurringTransaction]:
        result = await self._session.execute(
            select(RecurringTransaction)
            .options(selectinload(RecurringTransaction.category))
            .order_by(RecurringTransaction.day_of_month)
        )
        return result.scalars().all()

    async def list_active(self) -> Sequence[RecurringTransaction]:
        result = await self._session.execute(
            select(RecurringTransaction)
            .options(selectinload(RecurringTransaction.category))
            .where(RecurringTransaction.active == True)
        )
        return result.scalars().all()

    async def create(self, rec: RecurringTransaction) -> RecurringTransaction:
        self._session.add(rec)
        await self._session.commit()
        await self._session.refresh(rec)
        result = await self._session.execute(
            select(RecurringTransaction).options(selectinload(RecurringTransaction.category)).where(RecurringTransaction.id == rec.id)
        )
        return result.scalar_one()

    async def delete(self, rec_id: int) -> None:
        rec = await self._session.get(RecurringTransaction, rec_id)
        if not rec:
            raise NotFoundError(f"Recurring {rec_id} not found")
        await self._session.delete(rec)
        await self._session.commit()
