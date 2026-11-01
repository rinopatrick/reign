"""Transaction API routes."""

import csv
import io
import json
from datetime import date as date_cls

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reign.adapters.database import get_session
from reign.adapters.repository import AccountRepository, CategoryRepository, TransactionRepository
from reign.api.schemas import (
    BulkIds,
    BulkUpdate,
    CSVImportResponse,
    TransactionCreate,
    TransactionListParams,
    TransactionOut,
    TransferCreate,
)
from reign.config import settings
from reign.domain.models import Transaction, TransactionSplit
from reign.exceptions import CSVParseError, NotFoundError
from reign.services.categorizer import categorize_transactions
from reign.services.csv_parser import parse_csv
from reign.services.uploads import read_limited_upload

router = APIRouter()


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    params: TransactionListParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    repo = TransactionRepository(session)
    return await repo.list(
        account_id=params.account_id,
        category_id=params.category_id,
        start_date=params.start_date,
        end_date=params.end_date,
        q=params.q,
        tag=params.tag,
        limit=params.limit,
        offset=params.offset,
        after_id=params.after_id,
    )


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(data: TransactionCreate, session: AsyncSession = Depends(get_session)):
    try:
        await AccountRepository(session).get(data.account_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    repo = TransactionRepository(session)
    tx = Transaction(**{k: v for k, v in data.model_dump().items() if k != "splits"})
    splits = None
    if data.splits:
        splits = [
            TransactionSplit(
                category_id=s.category_id,
                amount=s.amount,
                description=s.description,
            )
            for s in data.splits
        ]
    return await repo.create(tx, splits=splits)


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(transaction_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Transaction)
        .options(
            selectinload(Transaction.category),
            selectinload(Transaction.splits).selectinload(TransactionSplit.category),
        )
        .where(Transaction.id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.put("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: int,
    data: TransactionCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        await AccountRepository(session).get(data.account_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    repo = TransactionRepository(session)
    update_data = {k: v for k, v in data.model_dump().items() if k != "splits"}
    splits = None
    if data.splits is not None:
        splits = [
            TransactionSplit(
                category_id=s.category_id,
                amount=s.amount,
                description=s.description,
            )
            for s in data.splits
        ]
    try:
        return await repo.update(transaction_id, update_data, splits=splits)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/transfer", status_code=201)
async def create_transfer(data: TransferCreate, session: AsyncSession = Depends(get_session)):
    """Create a transfer between two accounts."""
    if data.from_account_id == data.to_account_id:
        raise HTTPException(status_code=400, detail="Transfer accounts must differ")
    try:
        await AccountRepository(session).get(data.from_account_id)
        await AccountRepository(session).get(data.to_account_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    repo = TransactionRepository(session)
    from_tx = Transaction(
        date=data.date,
        description=data.description or f"Transfer to account {data.to_account_id}",
        amount=-abs(data.amount),
        currency=data.currency,
        account_id=data.from_account_id,
        transaction_type="transfer",
        tags="transfer",
    )
    to_tx = Transaction(
        date=data.date,
        description=data.description or f"Transfer from account {data.from_account_id}",
        amount=abs(data.amount),
        currency=data.currency,
        account_id=data.to_account_id,
        transaction_type="transfer",
        tags="transfer",
    )
    from_tx, to_tx = await repo.create_transfer(from_tx, to_tx)
    return {
        "message": "Transfer created",
        "from_transaction": TransactionOut.model_validate(from_tx),
        "to_transaction": TransactionOut.model_validate(to_tx),
    }


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: int, session: AsyncSession = Depends(get_session)):
    repo = TransactionRepository(session)
    try:
        await repo.delete(transaction_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "Transaction deleted"}


@router.post("/bulk-delete")
async def bulk_delete(data: BulkIds, session: AsyncSession = Depends(get_session)):
    repo = TransactionRepository(session)
    await repo.bulk_delete(data.ids)
    return {"message": f"Deleted {len(data.ids)} transactions"}


@router.post("/bulk-reconcile")
async def bulk_reconcile(data: BulkIds, session: AsyncSession = Depends(get_session)):
    repo = TransactionRepository(session)
    await repo.bulk_reconcile(data.ids)
    return {"message": f"Reconciled {len(data.ids)} transactions"}


@router.post("/bulk-update")
async def bulk_update(data: BulkUpdate, session: AsyncSession = Depends(get_session)):
    repo = TransactionRepository(session)
    if data.category_id is not None:
        try:
            await CategoryRepository(session).get(data.category_id)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
    await repo.bulk_update(data.ids, category_id=data.category_id, date=data.date)
    return {"message": f"Updated {len(data.ids)} transactions"}


@router.post("/import", response_model=CSVImportResponse)
async def import_csv(
    account_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload a bank CSV and auto-import transactions."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    if file.size is not None and file.size > settings.max_csv_bytes:
        raise HTTPException(status_code=413, detail="CSV too large (max 5MB)")
    try:
        await AccountRepository(session).get(account_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    content = await read_limited_upload(file, settings.max_csv_bytes, "CSV")
    try:
        fmt, parsed = parse_csv(content)
    except CSVParseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    repo = TransactionRepository(session)
    transactions: list[Transaction] = []
    for item in parsed:
        date_val = item["date"]
        if isinstance(date_val, str):
            date_val = date_cls.fromisoformat(date_val)
        tx = Transaction(
            date=date_val,
            description=item["description"],
            amount=item["amount"],
            currency=item.get("currency", "IDR"),
            account_id=account_id,
        )
        transactions.append(tx)

    if transactions:
        await categorize_transactions(session, transactions)
        await repo.create_many(transactions)

    return CSVImportResponse(
        imported=len(transactions),
        skipped=0,
        message=f"Imported {len(transactions)} transactions from {fmt} format.",
    )


@router.post("/import-preview")
async def import_csv_preview(
    file: UploadFile = File(...),
):
    """Preview a CSV before importing — returns first 10 rows + detected format."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    if file.size is not None and file.size > settings.max_csv_bytes:
        raise HTTPException(status_code=413, detail="CSV too large (max 5MB)")
    content = await read_limited_upload(file, settings.max_csv_bytes, "CSV")
    try:
        fmt, parsed = parse_csv(content)
    except CSVParseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {
        "format": fmt,
        "preview": parsed[:10],
        "total": len(parsed),
    }


@router.get("/export/csv")
async def export_csv(
    account_id: int | None = None,
    start_date: date_cls | None = None,
    end_date: date_cls | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Export transactions as CSV."""
    repo = TransactionRepository(session)
    txs = await repo.list(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=2000,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "description",
            "amount",
            "currency",
            "category",
            "tags",
            "transaction_type",
            "account_id",
        ]
    )
    for tx in txs:
        writer.writerow(
            [
                tx.date.isoformat(),
                tx.description,
                str(tx.amount),
                tx.currency,
                tx.category.name if tx.category else "",
                tx.tags or "",
                tx.transaction_type,
                tx.account_id,
            ]
        )
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/export/json")
async def export_json(
    account_id: int | None = None,
    start_date: date_cls | None = None,
    end_date: date_cls | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Export transactions as JSON."""
    repo = TransactionRepository(session)
    txs = await repo.list(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=2000,
    )
    data = [
        {
            "id": tx.id,
            "date": tx.date.isoformat(),
            "description": tx.description,
            "amount": str(tx.amount),
            "currency": tx.currency,
            "category": tx.category.name if tx.category else None,
            "tags": tx.tags or "",
            "transaction_type": tx.transaction_type,
            "account_id": tx.account_id,
            "is_reconciled": tx.is_reconciled,
        }
        for tx in txs
    ]
    return StreamingResponse(
        io.BytesIO(json.dumps(data, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=transactions.json"},
    )
