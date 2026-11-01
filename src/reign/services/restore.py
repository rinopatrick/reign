"""Restore helpers — keeps the route thin (PLR0912/PLR0915 stay green)."""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from reign.domain.models import (
    Account,
    Budget,
    Category,
    Goal,
    RecurringTransaction,
    Transaction,
    TransactionSplit,
)

WIPE_TABLES = (
    "transaction_splits",
    "transactions",
    "budgets",
    "recurring_transactions",
    "goals",
    "accounts",
    "categories",
)


def restore_counts(data: dict) -> dict:
    """Count payload entries for dry-run + response."""
    return {
        "accounts": len(data.get("accounts", [])),
        "categories": len(data.get("categories", [])),
        "transactions": len(data.get("transactions", [])),
        "budgets": len(data.get("budgets", [])),
        "goals": len(data.get("goals", [])),
        "recurring": len(data.get("recurring", [])),
    }


def validate_backup_shape(data: object) -> dict:
    """Validate top-level shape + FK references; raise 422 on bad payload."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Invalid backup shape")
    cat_ids = {c.get("id") for c in data.get("categories", []) if isinstance(c, dict)}
    acc_ids = {a.get("id") for a in data.get("accounts", []) if isinstance(a, dict)}
    for t in data.get("transactions", []):
        if not isinstance(t, dict) or "description" not in t or "date" not in t:
            raise HTTPException(status_code=422, detail="Invalid transaction entry")
        if t.get("account_id") not in acc_ids:
            raise HTTPException(status_code=422, detail="Transaction references unknown account")
        if t.get("category_id") is not None and t.get("category_id") not in cat_ids:
            raise HTTPException(status_code=422, detail="Transaction references unknown category")
    try:
        for t in data.get("transactions", []):
            date.fromisoformat(str(t["date"]))
            Decimal(str(t.get("amount", "0")))
    except Exception as e:
        raise HTTPException(status_code=422, detail="Invalid transaction data") from e
    return data


async def wipe_tables(session: AsyncSession) -> None:
    """FK-safe wipe order: children first. Tables are a fixed allowlist."""
    for table in WIPE_TABLES:
        stmt = {
            "transaction_splits": text("DELETE FROM transaction_splits"),
            "transactions": text("DELETE FROM transactions"),
            "budgets": text("DELETE FROM budgets"),
            "recurring_transactions": text("DELETE FROM recurring_transactions"),
            "goals": text("DELETE FROM goals"),
            "accounts": text("DELETE FROM accounts"),
            "categories": text("DELETE FROM categories"),
        }[table]
        await session.execute(stmt)


async def restore_categories(session: AsyncSession, data: dict) -> dict:
    """Insert categories first (needed for FK); return old-id -> new-id map."""
    cat_map: dict = {}
    for c in data.get("categories", []):
        cat = Category(
            name=c["name"],
            type=c.get("type", "expense"),
            color=c.get("color"),
            keywords=c.get("keywords", ""),
        )
        session.add(cat)
        await session.flush()
        cat_map[c.get("id")] = cat.id
    return cat_map


async def restore_accounts(session: AsyncSession, data: dict) -> dict:
    """Insert accounts; return old-id -> new-id map."""
    acc_map: dict = {}
    for a in data.get("accounts", []):
        acc = Account(
            name=a["name"],
            type=a.get("type", "checking"),
            currency=a.get("currency", "IDR"),
            initial_balance=Decimal(str(a.get("initial_balance", 0))),
        )
        session.add(acc)
        await session.flush()
        acc_map[a.get("id")] = acc.id
    return acc_map


async def restore_transactions(
    session: AsyncSession, data: dict, cat_map: dict, acc_map: dict
) -> dict:
    """Insert transactions; return old-id -> new-id map."""
    tx_map: dict = {}
    for t in data.get("transactions", []):
        tx = Transaction(
            date=date.fromisoformat(str(t["date"])),
            description=t["description"],
            amount=Decimal(str(t["amount"])),
            currency=t.get("currency", "IDR"),
            account_id=acc_map.get(t.get("account_id"), t.get("account_id")),
            category_id=cat_map.get(t.get("category_id"), t.get("category_id"))
            if t.get("category_id") is not None
            else None,
            notes=t.get("notes", "") or "",
            tags=t.get("tags", "") or "",
            transaction_type=t.get("transaction_type", "expense"),
            is_deleted=bool(t.get("is_deleted", False)),
            is_reconciled=bool(t.get("is_reconciled", False)),
        )
        session.add(tx)
        await session.flush()
        tx_map[t.get("id")] = tx.id
    return tx_map


async def restore_children(
    session: AsyncSession, data: dict, cat_map: dict, acc_map: dict, tx_map: dict
) -> None:
    """Insert splits/budgets/goals/recurring (children of accounts/categories/tx)."""
    for s in data.get("splits", []):
        new_tx = tx_map.get(s.get("transaction_id"))
        if new_tx is None:
            continue
        new_cat = cat_map.get(s.get("category_id")) if s.get("category_id") is not None else None
        session.add(
            TransactionSplit(
                transaction_id=new_tx,
                category_id=new_cat,
                amount=Decimal(str(s.get("amount", 0))),
                description=s.get("description"),
            )
        )
    for b in data.get("budgets", []):
        new_cat = cat_map.get(b.get("category_id"), b.get("category_id"))
        if new_cat is None:
            continue
        session.add(
            Budget(
                year=int(b["year"]),
                month=int(b["month"]),
                amount=Decimal(str(b["amount"])),
                currency=b.get("currency", "IDR"),
                rollover=bool(b.get("rollover", False)),
                category_id=new_cat,
            )
        )
    for g in data.get("goals", []):
        session.add(
            Goal(
                name=g["name"],
                target_amount=Decimal(str(g["target_amount"])),
                current_amount=Decimal(str(g.get("current_amount", 0))),
                currency=g.get("currency", "IDR"),
            )
        )
    for r in data.get("recurring", []):
        new_acc = acc_map.get(r.get("account_id"), r.get("account_id"))
        new_cat = cat_map.get(r.get("category_id")) if r.get("category_id") is not None else None
        session.add(
            RecurringTransaction(
                description=r.get("description", ""),
                amount=Decimal(str(r.get("amount", 0))),
                currency=r.get("currency", "IDR"),
                day_of_month=int(r.get("day_of_month", 1)),
                category_id=new_cat,
                account_id=new_acc,
                active=bool(r.get("active", True)),
            )
        )


async def run_restore(session: AsyncSession, data: dict) -> None:
    """Full wipe + insert inside the caller's transaction."""
    await wipe_tables(session)
    cat_map = await restore_categories(session, data)
    acc_map = await restore_accounts(session, data)
    tx_map = await restore_transactions(session, data, cat_map, acc_map)
    await restore_children(session, data, cat_map, acc_map, tx_map)
