"""Transaction API routes."""
import csv
import io
import json
from datetime import date as date_cls

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session
from reign.adapters.repository import TransactionRepository
from reign.api.schemas import (
    BulkIds,
    BulkUpdate,
    CSVImportResponse,
    TransactionCreate,
    TransactionOut,
    TransferCreate,
)
from reign.domain.models import Transaction
from reign.exceptions import CSVParseError, NotFoundError
from reign.services.categorizer import categorize_transactions
from reign.services.csv_parser import parse_csv

router = APIRouter()


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    account_id: int | None = None,
    category_id: int | None = None,
    start_date: date_cls | None = None,
    end_date: date_cls | None = None,
    q: str | None = None,
    tag: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = TransactionRepository(session)
    return await repo.list(
        account_id=account_id,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
        q=q,
        tag=tag,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(
    data: TransactionCreate, session: AsyncSession = Depends(get_session)
):
    repo = TransactionRepository(session)
    tx = Transaction(**data.model_dump())
    return await repo.create(tx)


@router.post("/transfer", status_code=201)
async def create_transfer(
    data: TransferCreate, session: AsyncSession = Depends(get_session)
):
    """Create a transfer between two accounts."""
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
async def delete_transaction(
    transaction_id: int, session: AsyncSession = Depends(get_session)
):
    repo = TransactionRepository(session)
    try:
        await repo.delete(transaction_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "Transaction deleted"}


@router.post("/bulk-delete")
async def bulk_delete(
    data: BulkIds, session: AsyncSession = Depends(get_session)
):
    repo = TransactionRepository(session)
    await repo.bulk_delete(data.ids)
    return {"message": f"Deleted {len(data.ids)} transactions"}


@router.post("/bulk-reconcile")
async def bulk_reconcile(
    data: BulkIds, session: AsyncSession = Depends(get_session)
):
    repo = TransactionRepository(session)
    await repo.bulk_reconcile(data.ids)
    return {"message": f"Reconciled {len(data.ids)} transactions"}


@router.post("/bulk-update")
async def bulk_update(
    data: BulkUpdate, session: AsyncSession = Depends(get_session)
):
    repo = TransactionRepository(session)
    await repo.bulk_update(data.ids, category_id=data.category_id, date=data.date)
    return {"message": f"Updated {len(data.ids)} transactions"}


@router.post("/import", response_model=CSVImportResponse)
async def import_csv(
    account_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload a bank CSV and auto-import transactions."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    content = await file.read()
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
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    content = await file.read()
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
    writer.writerow(["date", "description", "amount", "currency", "category", "tags", "transaction_type", "account_id"])
    for tx in txs:
        writer.writerow([
            tx.date.isoformat(),
            tx.description,
            str(tx.amount),
            tx.currency,
            tx.category.name if tx.category else "",
            tx.tags or "",
            tx.transaction_type,
            tx.account_id,
        ])
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
