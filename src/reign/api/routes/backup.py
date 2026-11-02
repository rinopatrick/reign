"""Backup/restore API routes — hardened: full payload, size limits, dry-run + snapshot."""

import asyncio
import contextlib
import gzip
import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from reign.adapters.database import (
    DEFAULT_PROFILE,
    _data_root,
    get_session_factory,
    init_db,
    validate_slug,
)
from reign.adapters.repository import (
    AccountRepository,
    CategoryRepository,
    GoalRepository,
    TransactionListFilter,
    TransactionRepository,
)
from reign.api.routes.holdings import _fire_alert_if_hit
from reign.api.routes.profiles import _profiles_root
from reign.config import settings
from reign.domain.models import Budget, Holding, PricePoint, RecurringTransaction, TransactionSplit
from reign.exceptions import ProfileError
from reign.services.market import fetch_price
from reign.services.restore import restore_counts, run_restore, validate_backup_shape
from reign.services.settings import get_setting as _get_setting, set_setting as _set_setting
from reign.services.uploads import read_limited_upload

router = APIRouter()
logger = logging.getLogger("reign.backup")

BACKUPS_DIR = Path(os.getenv("REIGN_BACKUPS_DIR", settings.backups_dir))
MAX_AUTO_BACKUPS = 10


def _backups_dir(profile: str = "default") -> Path:
    if profile == "default":
        d = Path(os.getenv("REIGN_BACKUPS_DIR", settings.backups_dir))
    else:
        d = _data_root() / "profiles" / validate_slug(profile) / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


async def _collect_backup_data(session) -> dict:
    """Single place that builds the full backup payload (no duplication)."""
    accounts = await AccountRepository(session).list()
    categories = await CategoryRepository(session).list()
    tx_filters = TransactionListFilter(include_deleted=True)
    transactions = await TransactionRepository(session).list(tx_filters)
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


async def _collect_backup_json(session) -> bytes:
    """Serialize backup payload to compact JSON bytes."""
    data = await _collect_backup_data(session)
    return json.dumps(data, cls=DecimalEncoder).encode("utf-8")


async def _snapshot_current(session, backups_dir: Path) -> str:
    """Save pre-restore snapshot so a bad restore never loses user data."""
    data = await _collect_backup_data(session)
    snap = backups_dir / f"reign_prerestore_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    with snap.open("w", encoding="utf-8") as f:
        json.dump(data, f, cls=DecimalEncoder, indent=2)
    return str(snap)


async def do_auto_backup(profile: str = "default") -> str | None:
    """Export backup JSON to the profile backups/ folder. Returns filepath or None."""
    slug = validate_slug(profile)
    async with get_session_factory(slug)() as session:
        enabled = (await _get_setting(session, "auto_backup_enabled", "false")).lower() == "true"
        if not enabled:
            return None
        compress = (await _get_setting(session, "auto_backup_compress", "true")).lower() == "true"
        payload = await _collect_backup_json(session)

    backups_dir = _backups_dir(slug)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if compress:
        filepath = backups_dir / f"reign_auto_{stamp}.json.gz"
        filepath.write_bytes(gzip.compress(payload))
    else:
        filepath = backups_dir / f"reign_auto_{stamp}.json"
        with filepath.open("w", encoding="utf-8") as f:
            f.write(payload.decode("utf-8"))

    auto_backups = sorted(backups_dir.glob("reign_auto_*.json*"), key=lambda p: p.stat().st_mtime)
    for old in auto_backups[:-MAX_AUTO_BACKUPS]:
        old.unlink()

    async with get_session_factory(slug)() as session:
        await _set_setting(session, "auto_backup_last_run", datetime.now().isoformat())
    return str(filepath)


async def run_backup_cycle(slug: str) -> str | None:
    """One scheduler pass for a profile: skip when disabled, not due, or already archived today."""
    today = datetime.now().strftime("%Y-%m-%d")
    backups_dir = _backups_dir(slug)
    if any(
        p.name.startswith(f"reign_auto_{today}") for p in backups_dir.glob("reign_auto_*.json*")
    ):
        return None
    try:
        await init_db(slug)
    except Exception as e:
        logger.warning("Auto-backup skipped for profile %s: %s", slug, e)
        return None
    async with get_session_factory(slug)() as session:
        enabled = (await _get_setting(session, "auto_backup_enabled", "false")).lower() == "true"
        if not enabled:
            return None
        interval_days = int(await _get_setting(session, "auto_backup_interval_days", "7"))
        last_run_str = await _get_setting(session, "auto_backup_last_run", "")
        if last_run_str and datetime.now() - datetime.fromisoformat(last_run_str) < timedelta(
            days=interval_days
        ):
            return None
    return await do_auto_backup(slug)


async def backup_scheduler():
    """Background task: check every hour if backup is due (all profiles)."""
    await asyncio.sleep(30)  # Let app finish startup first
    while True:
        try:
            slugs = {DEFAULT_PROFILE}
            with contextlib.suppress(OSError):
                slugs |= {p.name for p in _profiles_root().iterdir() if p.is_dir()}
            for slug in sorted(slugs):
                try:
                    filepath = await run_backup_cycle(slug)
                except Exception as e:
                    logger.warning("Auto-backup skipped for profile %s: %s", slug, e)
                    continue
                if filepath:
                    logger.info("Auto-backup saved: %s", filepath)
        except Exception as e:
            logger.exception("Backup error: %s", e)
        await asyncio.sleep(3600)


async def market_scheduler(interval_hours: int = 24) -> None:
    """Background task: refresh all holdings' prices on a fixed interval."""
    await asyncio.sleep(60)
    while True:
        try:
            async with get_session_factory("default")() as session:
                rows = (await session.execute(select(Holding))).scalars().all()
                for h in rows:
                    price = await fetch_price(h.symbol)
                    if price is None:
                        continue
                    h.current_price = price
                    session.add(
                        PricePoint(holding_id=h.id, price=price, currency=h.currency or "IDR")
                    )
                    await _fire_alert_if_hit(session, h, price)
                await session.commit()
                if rows:
                    logger.info("Market refresh saved for %d holdings", len(rows))
        except Exception as e:
            logger.exception("Market refresh error: %s", e)
        await asyncio.sleep(interval_hours * 3600)


def _req_profile(request: Request) -> str:
    return validate_slug(request.headers.get("x-reign-profile", "") or "default")


@contextlib.asynccontextmanager
async def _session_for_request(request: Request):
    factory = get_session_factory(_req_profile(request))
    async with factory() as session:
        yield session


@router.get("/backup")
async def export_backup(request: Request):
    profile = _req_profile(request)
    await init_db(profile)
    async with _session_for_request(request) as session:
        data = await _collect_backup_data(session)
    return JSONResponse(
        content=json.loads(json.dumps(data, cls=DecimalEncoder)),
        headers={"Content-Disposition": "attachment; filename=backup.json"},
    )


@router.post("/restore")
async def import_backup(request: Request, file: UploadFile = File(...), *, dry_run: bool = False):
    name = (file.filename or "").lower()
    is_gzip = name.endswith(".json.gz")
    if not (name.endswith(".json") or is_gzip):
        raise HTTPException(status_code=400, detail="File must be JSON or JSON.GZ")
    raw_bytes = await read_limited_upload(file, settings.max_json_bytes, "Backup")
    if is_gzip:
        try:
            raw_bytes = gzip.decompress(raw_bytes)
        except OSError as e:
            raise HTTPException(status_code=422, detail="Invalid gzip") from e
        if len(raw_bytes) > settings.max_json_bytes:
            raise HTTPException(status_code=413, detail="Decompressed backup too large")
    try:
        raw = json.loads(raw_bytes)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail="Invalid JSON") from e
    data = validate_backup_shape(raw)
    counts = restore_counts(data)
    if dry_run:
        return {"message": "Dry run OK", "would_restore": counts}

    profile = _req_profile(request)
    async with _session_for_request(request) as session:
        backups_dir = _backups_dir(profile)
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
async def trigger_backup(request: Request):
    """Manually trigger an auto-backup (saves to backups/ folder)."""
    filepath = await do_auto_backup(_req_profile(request))
    if filepath:
        return {"message": "Backup saved", "path": filepath}
    return {"message": "Backup skipped — auto-backup is disabled"}


@router.get("/backup/history")
async def backup_history(request: Request, limit: int = 20):
    """List backup archives for the active profile (newest first)."""
    backups_dir = _backups_dir(_req_profile(request))
    files = sorted(
        [
            *backups_dir.glob("reign_auto_*.json*"),
            *backups_dir.glob("reign_prerestore_*.json"),
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: max(1, min(limit, 100))]
    return [{"name": f.name, "size": f.stat().st_size, "mtime": f.stat().st_mtime} for f in files]


class ProfileTransferIn(BaseModel):
    slug: str


@router.get("/profiles/export")
async def export_profile(request: Request):
    """Download one self-contained file: profile slug + full backup payload."""
    profile = _req_profile(request)
    await init_db(profile)
    async with _session_for_request(request) as session:
        data = await _collect_backup_data(session)
    payload = {"kind": "reign-profile", "version": 1, "profile": profile, "backup": data}
    return JSONResponse(
        content=json.loads(json.dumps(payload, cls=DecimalEncoder)),
        headers={"Content-Disposition": f"attachment; filename=reign_profile_{profile}.json"},
    )


@router.post("/profiles/import")
async def import_profile(payload: ProfileTransferIn, request: Request):
    """Clone the *current* profile's data into a new profile slug (sync/copy)."""
    try:
        target = validate_slug(payload.slug)
    except ProfileError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    source = _req_profile(request)
    if target == source:
        raise HTTPException(status_code=400, detail="Target profile equals current profile")
    await init_db(source)
    await init_db(target)
    async with _session_for_request(request) as session:
        data = await _collect_backup_data(session)
    factory = get_session_factory(target)
    async with factory() as ts:
        backups_dir = _backups_dir(target)
        snapshot_path = await _snapshot_current(ts, backups_dir)
        try:
            await run_restore(ts, data)
            await ts.commit()
        except Exception as e:
            await ts.rollback()
            logger.exception("Profile import failed, rolled back: %s", e)
            raise HTTPException(status_code=422, detail="Profile import failed") from e
    return {"message": "Profile imported", "from": source, "to": target, "snapshot": snapshot_path}
