"""Backup/restore API routes — hardened: full payload, size limits, dry-run + snapshot."""

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select

from reign.adapters.database import AsyncSessionLocal
from reign.adapters.repository import (
    AccountRepository,
    CategoryRepository,
    GoalRepository,
    TransactionRepository,
)
from reign.config import settings
from reign.domain.models import (
    Account,
    AppSetting,
    Budget,
    Category,
    Goal,
    RecurringTransaction,
    Transaction,
    TransactionSplit,
)

router = APIRouter()
logger = logging.getLogger("reign.backup")

BACKUPS_DIR = Path(os.getenv("REIGN_BACKUPS_DIR", settings.backups_dir))
MAX_AUTO_BACKUPS = 10


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def _backups_dir() -> Path:
    d = Path(os.getenv("REIGN_BACKUPS_DIR", settings.backups_dir))
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _get_setting(session, key: str, default: str = "") -> str:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = AppSetting(key=key, value=default)
        session.add(row)
        await session.commit()
    return row.value or ""


async def _set_setting(session, key: str, value: str) -> None:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    await session.commit()


async def _collect_backup_data(session) -> dict:
    """Single place that builds the full backup payload (no duplication)."""
    from sqlalchemy.orm import selectinload

    accounts = await AccountRepository(session).list()
    categories = await CategoryRepository(session).list()
    transactions = await TransactionRepository(session).list(include_deleted=True)
    goals = await GoalRepository(session).list()
    result = await session.execute(select(Budget))
    budgets = result.scalars().all()
    result = await session.execute(
        select(RecurringTransaction).options(selectinload(RecurringTransaction.category))
    )
    recurring = result.scalars().all()
    result = await session.execute(select(TransactionSplit))
    splits = result.scalars().all()
    return {
        "version": 2,
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "currency": a.currency,
                "initial_balance": a.initial_balance,
            }
            for a in accounts
        ],
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "color": c.color,
                "keywords": c.keywords,
            }
            for c in categories
        ],
        "transactions": [
            {
                "id": t.id,
                "date": str(t.date),
                "description": t.description,
                "amount": t.amount,
                "currency": t.currency,
                "account_id": t.account_id,
                "category_id": t.category_id,
                "notes": t.notes or "",
                "tags": t.tags or "",
                "transaction_type": t.transaction_type,
                "is_deleted": t.is_deleted,
                "is_reconciled": t.is_reconciled,
            }
            for t in transactions
        ],
        "splits": [
            {
                "id": s.id,
                "transaction_id": s.transaction_id,
                "category_id": s.category_id,
                "amount": s.amount,
                "description": s.description,
            }
            for s in splits
        ],
        "budgets": [
            {
                "id": b.id,
                "year": b.year,
                "month": b.month,
                "amount": b.amount,
                "currency": b.currency,
                "rollover": b.rollover,
                "category_id": b.category_id,
            }
            for b in budgets
        ],
        "goals": [
            {
                "id": g.id,
                "name": g.name,
                "target_amount": g.target_amount,
                "current_amount": g.current_amount,
                "currency": g.currency,
            }
            for g in goals
        ],
        "recurring": [
            {
                "id": r.id,
                "description": r.description,
                "amount": r.amount,
                "currency": r.currency,
                "day_of_month": r.day_of_month,
                "category_id": r.category_id,
                "account_id": r.account_id,
                "active": r.active,
            }
            for r in recurring
        ],
    }


async def _snapshot_current(session, backups_dir: Path) -> str:
    """Save pre-restore snapshot so a bad restore never loses user data."""
    data = await _collect_backup_data(session)
    snap = backups_dir / f"reign_prerestore_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    with snap.open("w", encoding="utf-8") as f:
        json.dump(data, f, cls=DecimalEncoder, indent=2)
    return str(snap)


async def do_auto_backup() -> str | None:
    """Export backup JSON to backups/ folder. Returns filepath or None."""
    async with AsyncSessionLocal() as session:
        enabled = (await _get_setting(session, "auto_backup_enabled", "false")).lower() == "true"
        if not enabled:
            return None
        data = await _collect_backup_data(session)

    backups_dir = _backups_dir()
    filepath = backups_dir / f"reign_auto_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, cls=DecimalEncoder, indent=2)

    auto_backups = sorted(backups_dir.glob("reign_auto_*.json"), key=lambda p: p.stat().st_mtime)
    for old in auto_backups[:-MAX_AUTO_BACKUPS]:
        old.unlink()

    async with AsyncSessionLocal() as session:
        await _set_setting(session, "auto_backup_last_run", datetime.now().isoformat())
    return str(filepath)


async def backup_scheduler():
    """Background task: check every hour if backup is due."""
    await asyncio.sleep(30)  # Let app finish startup first
    while True:
        try:
            async with AsyncSessionLocal() as session:
                enabled = (await _get_setting(session, "auto_backup_enabled", "false")).lower() == "true"
                if not enabled:
                    await asyncio.sleep(3600)
                    continue
                interval_days = int(await _get_setting(session, "auto_backup_interval_days", "7"))
                last_run_str = await _get_setting(session, "auto_backup_last_run", "")
                if last_run_str:
                    last_run = datetime.fromisoformat(last_run_str)
                    if datetime.now() - last_run < timedelta(days=interval_days):
                        await asyncio.sleep(3600)
                        continue
            filepath = await do_auto_backup()
            if filepath:
                logger.info("Auto-backup saved: %s", filepath)
        except Exception as e:
            logger.exception("Backup error: %s", e)
        await asyncio.sleep(3600)


@router.get("/backup")
async def export_backup():
    async with AsyncSessionLocal() as session:
        data = await _collect_backup_data(session)
    return JSONResponse(
        content=json.loads(json.dumps(data, cls=DecimalEncoder)),
        headers={"Content-Disposition": "attachment; filename=backup.json"},
    )


@router.post("/restore")
async def import_backup(file: UploadFile = File(...), dry_run: bool = False):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be JSON")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_json_bytes:
            raise HTTPException(status_code=413, detail="Backup too large (max 10MB)")
        chunks.append(chunk)
    content = b"".join(chunks)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail="Invalid JSON") from e
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Invalid backup shape")

    # Validate FK references before touching the DB.
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

    counts = {
        "accounts": len(data.get("accounts", [])),
        "categories": len(data.get("categories", [])),
        "transactions": len(data.get("transactions", [])),
        "budgets": len(data.get("budgets", [])),
        "goals": len(data.get("goals", [])),
        "recurring": len(data.get("recurring", [])),
    }
    if dry_run:
        return {"message": "Dry run OK", "would_restore": counts}

    async with AsyncSessionLocal() as session:
        backups_dir = _backups_dir()
        snapshot_path = await _snapshot_current(session, backups_dir)
        try:
            from sqlalchemy import text as _text

            # FK-safe wipe order: children first.
            for tbl in (
                "transaction_splits",
                "transactions",
                "budgets",
                "recurring_transactions",
                "goals",
                "accounts",
                "categories",
            ):
                await session.execute(_text(f"DELETE FROM {tbl}"))
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
            for s in data.get("splits", []):
                # Old backups (v1) have no splits — skip gracefully.
                new_tx = tx_map.get(s.get("transaction_id"))
                new_cat = cat_map.get(s.get("category_id")) if s.get("category_id") is not None else None
                if new_tx is None:
                    continue
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
            await session.commit()
        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.exception("Restore failed, rolled back: %s", e)
            raise HTTPException(status_code=422, detail="Restore failed, no data changed") from e

    return {
        "message": "Restore complete",
        "accounts": counts["accounts"],
        "categories": counts["categories"],
        "transactions": counts["transactions"],
        "snapshot": snapshot_path,
    }


@router.post("/backup/trigger")
async def trigger_backup():
    """Manually trigger an auto-backup (saves to backups/ folder)."""
    filepath = await do_auto_backup()
    if filepath:
        return {"message": "Backup saved", "path": filepath}
    return {"message": "Backup skipped — auto-backup is disabled"}
