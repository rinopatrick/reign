"""Backup/restore API routes."""
import asyncio
import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from reign.adapters.database import AsyncSessionLocal
from reign.adapters.repository import (
    AccountRepository,
    CategoryRepository,
    GoalRepository,
    TransactionRepository,
)
from reign.domain.models import Account, AppSetting, Category, Goal, Transaction

router = APIRouter()

BACKUPS_DIR = Path("./backups")
MAX_AUTO_BACKUPS = 10


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


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


async def do_auto_backup() -> str | None:
    """Export backup JSON to backups/ folder. Returns filepath or None."""
    async with AsyncSessionLocal() as session:
        enabled = (await _get_setting(session, "auto_backup_enabled", "false")).lower() == "true"
        if not enabled:
            return None

        accounts = await AccountRepository(session).list()
        categories = await CategoryRepository(session).list()
        transactions = await TransactionRepository(session).list(include_deleted=True)
        goals = await GoalRepository(session).list()

    data = {
        "accounts": [{"id": a.id, "name": a.name, "type": a.type, "currency": a.currency, "initial_balance": a.initial_balance} for a in accounts],
        "categories": [{"id": c.id, "name": c.name, "type": c.type, "color": c.color, "keywords": c.keywords} for c in categories],
        "transactions": [{"id": t.id, "date": str(t.date), "description": t.description, "amount": t.amount, "currency": t.currency, "account_id": t.account_id, "category_id": t.category_id, "is_reconciled": t.is_reconciled} for t in transactions],
        "goals": [{"id": g.id, "name": g.name, "target_amount": g.target_amount, "current_amount": g.current_amount, "currency": g.currency} for g in goals],
    }

    BACKUPS_DIR.mkdir(exist_ok=True)
    filepath = BACKUPS_DIR / f"reign_auto_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, cls=DecimalEncoder, indent=2)

    # Clean old auto-backups
    auto_backups = sorted(BACKUPS_DIR.glob("reign_auto_*.json"), key=lambda p: p.stat().st_mtime)
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
                print(f"[scheduler] Auto-backup saved: {filepath}")
        except Exception as e:
            print(f"[scheduler] Backup error: {e}")

        await asyncio.sleep(3600)


@router.get("/backup")
async def export_backup():
    async with AsyncSessionLocal() as session:
        accounts = await AccountRepository(session).list()
        categories = await CategoryRepository(session).list()
        transactions = await TransactionRepository(session).list(include_deleted=True)
        goals = await GoalRepository(session).list()

    data = {
        "accounts": [{"id": a.id, "name": a.name, "type": a.type, "currency": a.currency, "initial_balance": a.initial_balance} for a in accounts],
        "categories": [{"id": c.id, "name": c.name, "type": c.type, "color": c.color, "keywords": c.keywords} for c in categories],
        "transactions": [{"id": t.id, "date": str(t.date), "description": t.description, "amount": t.amount, "currency": t.currency, "account_id": t.account_id, "category_id": t.category_id, "is_reconciled": t.is_reconciled} for t in transactions],
        "goals": [{"id": g.id, "name": g.name, "target_amount": g.target_amount, "current_amount": g.current_amount, "currency": g.currency} for g in goals],
    }
    return JSONResponse(
        content=json.loads(json.dumps(data, cls=DecimalEncoder)),
        headers={"Content-Disposition": "attachment; filename=backup.json"}
    )


@router.post("/restore")
async def import_backup(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be JSON")
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {e}")

    async with AsyncSessionLocal() as session:
        # Clear existing data
        await session.execute(text("DELETE FROM transactions"))
        await session.execute(text("DELETE FROM budgets"))
        await session.execute(text("DELETE FROM goals"))
        await session.execute(text("DELETE FROM accounts"))
        await session.execute(text("DELETE FROM categories"))
        await session.commit()

        # Restore categories first (needed for FK)
        cat_map = {}
        for c in data.get("categories", []):
            cat = Category(name=c["name"], type=c.get("type", "expense"), color=c.get("color"), keywords=c.get("keywords", ""))
            session.add(cat)
            await session.flush()
            cat_map[c["id"]] = cat.id

        # Restore accounts
        acc_map = {}
        for a in data.get("accounts", []):
            acc = Account(name=a["name"], type=a.get("type", "checking"), currency=a.get("currency", "IDR"), initial_balance=Decimal(str(a.get("initial_balance", 0))))
            session.add(acc)
            await session.flush()
            acc_map[a["id"]] = acc.id

        # Restore transactions
        for t in data.get("transactions", []):
            old_acc_id = t.get("account_id")
            old_cat_id = t.get("category_id")
            tx = Transaction(
                date=date.fromisoformat(t["date"]),
                description=t["description"],
                amount=Decimal(str(t["amount"])),
                currency=t.get("currency", "IDR"),
                account_id=acc_map.get(old_acc_id, old_acc_id),
                category_id=cat_map.get(old_cat_id, old_cat_id) if old_cat_id else None,
                is_reconciled=t.get("is_reconciled", False),
            )
            session.add(tx)

        # Restore goals
        for g in data.get("goals", []):
            goal = Goal(
                name=g["name"],
                target_amount=Decimal(str(g["target_amount"])),
                current_amount=Decimal(str(g.get("current_amount", 0))),
                currency=g.get("currency", "IDR"),
            )
            session.add(goal)

        await session.commit()

    return {"message": "Restore complete", "accounts": len(acc_map), "categories": len(cat_map), "transactions": len(data.get("transactions", []))}


@router.post("/backup/trigger")
async def trigger_backup():
    """Manually trigger an auto-backup (saves to backups/ folder)."""
    filepath = await do_auto_backup()
    if filepath:
        return {"message": "Backup saved", "path": filepath}
    return {"message": "Backup skipped — auto-backup is disabled"}
