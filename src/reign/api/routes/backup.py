"""Backup/restore API routes — hardened: full payload, size limits, dry-run + snapshot."""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from reign.adapters.database import AsyncSessionLocal
from reign.adapters.repository import (
    AccountRepository,
    CategoryRepository,
    GoalRepository,
    TransactionListFilter,
    TransactionRepository,
)
from reign.config import settings
from reign.domain.models import Budget, RecurringTransaction, TransactionSplit
from reign.services.restore import restore_counts, run_restore, validate_backup_shape
from reign.services.settings import get_setting as _get_setting, set_setting as _set_setting
from reign.services.uploads import read_limited_upload

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


async def _collect_backup_data(session) -> dict:
    """Single place that builds the full backup payload (no duplication)."""
    accounts = await AccountRepository(session).list()
    categories = await CategoryRepository(session).list()
    transactions = await TransactionRepository(session).list(
        TransactionListFilter(include_deleted=True)
    )
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
                enabled = (
                    await _get_setting(session, "auto_backup_enabled", "false")
                ).lower() == "true"
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
async def import_backup(file: UploadFile = File(...), *, dry_run: bool = False):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be JSON")
    content = await read_limited_upload(file, settings.max_json_bytes, "Backup")
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail="Invalid JSON") from e
    data = validate_backup_shape(raw)
    counts = restore_counts(data)
    if dry_run:
        return {"message": "Dry run OK", "would_restore": counts}

    async with AsyncSessionLocal() as session:
        backups_dir = _backups_dir()
        snapshot_path = await _snapshot_current(session, backups_dir)
        try:
            await run_restore(session, data)
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
